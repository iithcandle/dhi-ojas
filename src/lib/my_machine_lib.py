#!/usr/bin/env python3

#
# Copyright (C) 2018-2022 Maruthi Seshidhar Inukonda - All Rights Reserved.
# maruthi.inukonda@gmail.com
#
# This file is released under the Affero GPLv3 License.
#

import asyncio
import time
from datetime import datetime,timedelta,timezone
import multiprocessing
import subprocess
import os
import json

class MachineFactory:
	def __init__(self):
		self._creators = {}

	def register_type(self, sys_prod, creator):
		#print("Registering ", sys_prod)
		self._creators[sys_prod] = creator

	def get_type(self, sys_prod, mach):
		creator = self._creators.get(sys_prod)
		if not creator:
			raise ValueError(sys_prod)
		return creator(mach)

class Machine:
	def __init__(self, mach):
		self.system_product = mach['system_product']
		#print("system_product:", self.system_product)
		self.mach = mach
		self.hostname = self.mach['hostname']
		self.loop = asyncio.get_event_loop()
		if self.mach['power_driver'] == "LAN_2_0":
			self.interface = "lanplus"
		elif self.mach['power_driver'] == "LAN":
			self.interface = "lan"
		self.bmc_data = dict()
		self.host_data = dict()
		self.bmc_cmds = dict()
		self.bmc_cmds['dcmi_power'] = ['ipmitool', '-I', self.interface, '-c',
			'-U', self.mach['power_user'], '-P', self.mach['power_pass'],
			'-H', self.mach['power_address'], 'dcmi', 'power', 'reading']
		self.bmc_funcs = [ self.run_dcmi_power_reading ]
		self.cpu_power = list()
		self.bmc_run_window = 1 # sec
		self.inlet_temp = list()
		self.outlet_temp = list()
		self.fan_speed = list()
		self.gpu_power = list()
		self.gpu_temp = list()
		self.fan_power = list()
		self.hdd_power = list()
		self.systemboard_power = list()
		self.total_power = list()
		self.switch_interval = 3600

	def __del__(self):
		self.loop.close()
		pass

	async def call_cmd(self, *cmd):
		#print('Starting {}'.format(cmd), 'type(cmd):', type(cmd))
		# Create subprocess
		process = await asyncio.create_subprocess_exec(
			*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
		)

		# Status
		#print("Started: ", *cmd, "pid=%s" %(process.pid), flush=True)

		# Wait for the subprocess to finish
		stdout, stderr = await process.communicate()

		# Progress
		if process.returncode == 0:
			'''
			print(
				"Done:", *cmd, "pid=%s, result: %s"
				%(process.pid, stdout.decode().strip()),
				flush=True,
			)
			'''
			pass
		else:
			'''
			print(
				"Failed:", *cmd, "pid=%s, result: %s"
				%(process.pid, stderr.decode().strip()),
				flush=True,
			)
			'''
			pass

		# Result
		result = stdout.decode().strip()

		# Return stdout
		return result

	def fetch_host_data(self, ts, outdir, skip_host, wtype, wl, queue):
		if 'user' not in self.mach or not self.mach['user'] or len(self.mach['user']) == 0:
			return
		#print("fetching host_data from", self.system_product)
		# Temporary return
		if skip_host:
			time.sleep(20)
			return

		time.sleep(self.bmc_run_window - datetime.utcnow().timestamp() % self.bmc_run_window)

		p = subprocess.run(['ssh', '-o', 'StrictHostKeyChecking=no',
			'-o', 'UserKnownHostsFile=/dev/null', '-f',
			'%s@%s' %(self.mach['user'], self.mach['ip_address']),
			"uc_fetchd", "--op", "start",
			"--daemon"], timeout=60)
		if p.returncode != 0:
			print("host data fetch failed")
			return

		i = 0
		seq = 0
		self.host_data = dict()
		while queue.empty():
			start_tm = datetime.utcnow()
			#print("start_tm:", str(start_tm))
			switch = int(start_tm.timestamp() % self.switch_interval)

			out_hand = open("/tmp/%s-outfile.json" %(self.hostname), "wt")
			err_hand = open("/tmp/%s-errfile.txt" %(self.hostname), "wt")
			p = subprocess.run(['ssh', '-o', 'StrictHostKeyChecking=no',
				'-o', 'UserKnownHostsFile=/dev/null',
				'%s@%s' %(self.mach['user'], self.mach['ip_address']),
				"uc_fetchd", "--op", "query"],
				stdout=out_hand, stderr=err_hand, timeout=60)
			out_hand.close()
			err_hand.close()
			if p.returncode != 0:
				print("failed to query uc_fetchd")
				continue

			data = dict()
			fh = open("/tmp/%s-outfile.json" %(self.hostname), "rt")
			output = fh.read()
			if len(output) != 0:
				data = json.loads(output)
			fh.close()
			for k,v in data.items():
				#print("K:", k, "v:", v)
				cpuload = v['cpuload_total']
				if cpuload < 0:
					util = -1
				elif cpuload > 0:
					util = 1
				else:
					util = 0
				v['util'] = util
				self.host_data[k] =  v
				print(self.hostname, "[", k, "]:", self.host_data[k])

			i += 1
			if switch == 0:
				host_data_file = os.path.join(outdir,"%s_%03d-%s-%s-%s-host_data.json" %(ts, seq, self.hostname, wl, wtype))
				fh = open(host_data_file, "wt")
				json.dump(self.host_data, fh, indent=4)
				fh.close()
				self.host_data = dict()
				seq += 1
				i = 0

			end_tm = datetime.utcnow()
			#print("host elapsed:", end_tm - start_tm)
			time.sleep(self.bmc_run_window - end_tm.timestamp() % self.bmc_run_window)

		host_data_file = os.path.join(outdir,"%s_%03d-%s-%s-%s-host_data.json" %(ts, seq, self.hostname, wl, wtype))
		fh = open(host_data_file, "wt")
		json.dump(self.host_data, fh, indent=4)
		fh.close()
		self.host_data = dict()

	def fetch_bmc_data(self, ts, outdir, wtype, wl, queue, bmc_type='closed'):
		# Only powered on systems' agent is reachable.
		if ( 'power_pass' not in self.mach or
			'power_user' not in self.mach or
			'power_driver' not in self.mach or
			'power_address' not in self.mach ):
			return
		#print("fetching bmc_data from", self.system_product)
		'''
		self.bmc_cmds['sdr'] = ['ipmitool', '-I', self.interface, '-c',
			'-U', self.mach['power_user'], '-P', self.mach['power_pass'],
			'-H', self.mach['power_address'], 'sdr']
		'''
		time.sleep(self.bmc_run_window - datetime.utcnow().timestamp() % self.bmc_run_window)

		i = 0
		seq = 0
		self.bmc_data = dict()
		while queue.empty():
			start_tm = datetime.utcnow()
			#print("start_tm:", str(start_tm))
			# Temporary hack to not split bmc_data into hourly files
			# TODO once benchmarking is made to use uc_fetchd, remove this hack.
			if wtype == "production":
				switch = int(start_tm.timestamp() % self.switch_interval)
			else:
				switch = 1

			i += 1
			if switch == 0:
				bmc_data_file = os.path.join(outdir,"%s_%03d-%s-%s-%s-bmc_data.json" %(ts, seq, self.hostname, wl, wtype))
				fh = open(bmc_data_file, "wt")
				json.dump(self.bmc_data, fh, indent=4)
				fh.close()
				self.bmc_data = dict()
				seq += 1
				i = 0

			# Run BMC commands serially, as BMC f/w does not have parallel ipmi cmd support
			for func in self.bmc_funcs:
				func(start_tm)

			end_tm = datetime.utcnow()
			if bmc_type == 'closed':
				print(self.hostname, "[", start_tm, "]:", self.bmc_data[str(start_tm)])

			#print("bmc elapsed:", end_tm - start_tm)
			time.sleep(self.bmc_run_window - end_tm.timestamp() % self.bmc_run_window)

		bmc_data_file = os.path.join(outdir,"%s_%03d-%s-%s-%s-bmc_data.json" %(ts, seq, self.hostname, wl, wtype))
		fh = open(bmc_data_file, "wt")
		json.dump(self.bmc_data, fh, indent=4)
		fh.close()
		self.bmc_data = dict()


	def run_dcmi_power_reading(self, tm):
		power_reading = -1
		proc = subprocess.Popen(self.bmc_cmds['dcmi_power'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		stdout, stderr = proc.communicate()
		if len(stdout) == 0:
			print("ipmitool dcmi power reading command failed on ", self.hostname)
			power_reading = -2
			self.bmc_data[str(tm)] =  { 'power': power_reading }
			return

		# get required statistics
		out = stdout.decode('utf-8').splitlines()
		# First line contains "Instantaneous power reading: x Watts"
		# Fourth line contains "Average power reading over sample period: x Watts"
		for line in out:
			if line.find("Average power reading over sample period") < 0:
				continue
			reading_units = line.split(':')[1]
			#print('reading_units:', reading_units)
			power_reading = float(reading_units.split()[0])
			break

		self.bmc_data[str(tm)] =  { 'power': power_reading }
		#print(self.hostname, "[", start_tm, "]:", self.bmc_data[str(start_tm)])

	def run_sensor_reading(self, tm):
		obj = {}
		proc = subprocess.Popen(self.bmc_cmds['sensor_reading'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		stdout, stderr = proc.communicate()
		if len(stdout) == 0:
			print("ipmitool sensor reading command failed on ", self.hostname)
			power_reading = -2
			self.bmc_data[str(tm)] =  { 'power': power_reading }
			return
		# get required statistics
		out = stdout.decode('utf-8').splitlines()
		#print(out)
		# other params
		cpu_power=-1
		for sensor in out:
			sensor = sensor.split(',')
			if (sensor[0] in self.inlet_temp):
				obj['inlet_temp'] = float(sensor[1])
			elif (sensor[0] in self.outlet_temp):
				obj['exhaust_temp'] = float(sensor[1])
			elif (sensor[0] in self.fan_speed):
				obj[sensor[0]] = float(sensor[1])
			elif (sensor[0] in self.cpu_power):
				if cpu_power == -1:
					cpu_power = float(sensor[1])
				else:
					cpu_power += float(sensor[1])
			elif (sensor[0] in self.gpu_power):
				obj[sensor[0]] = float(sensor[1])
			elif (sensor[0] in self.gpu_temp):
				obj[sensor[0]] = float(sensor[1])
			elif (sensor[0] in self.fan_power):
				obj['fan_power'] = float(sensor[1])
			elif (sensor[0] in self.hdd_power):
				obj['hdd_power'] = float(sensor[1])
			elif (sensor[0] in self.systemboard_power):
				obj['systemboard_power'] = float(sensor[1])
			elif (sensor[0] in self.total_power):
				obj[sensor[0]] = float(sensor[1])

		if cpu_power != -1 :
			obj['cpu_power'] = cpu_power
		for k,v in obj.items():
			self.bmc_data[str(tm)][k] = v

	def run_sensor_reading_openbmc(self, tm):
		out_hand = open("/tmp/%s-bmc-outfile.json" %(self.hostname), "wt")
		err_hand = open("/tmp/%s-bmc-errfile.txt" %(self.hostname), "wt")
		try:
			p = subprocess.run(self.bmc_cmds['sensor_reading'],stdout=out_hand, stderr=err_hand, timeout=10)
		except subprocess.TimeoutExpired:
			return

		out_hand.close()
		err_hand.close()

		#if p.returncode != 0:
		#	print("failed to query bmc_fetchd")

		data = dict()
		fh = open("/tmp/%s-bmc-outfile.json" %(self.hostname), "rt")
		output = fh.read()
		#print("output",output)
		output = output.replace('}{', ',')

		if ((len(output) != 0) and (output != '\n')):
			data = json.loads(output)
		else:
			#print("returned")
			return

		fh.close()
		for k,v in data.items():
			self.bmc_data[k] = v
			print(self.hostname, "[", k, "]:", self.bmc_data[k])
		'''
		obj = {}
		print(1)
		proc = subprocess.Popen(self.bmc_cmds['sensor_reading'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		print(2)
		stdout, stderr = proc.communicate(timeout = 5)
		print(3)
		if len(stdout) == 0:
			print("openbmc sensor reading command failed on ", self.hostname)
			power_reading = -2
			self.bmc_data[str(tm)] =  { 'power': power_reading }
			return
		# get required statistics
		out = ''.join(stdout.decode('utf-8').splitlines())
		print("out 1",out)
		out = out.replace('}{', ',')
		print("out 2",out)
		obj = json.loads(out)
		print(obj)
		for k,v in obj.items():
			self.bmc_data[k] = v
		'''


# "PowerEdge R630 (SKU=NotProvided;ModelName=PowerEdge R630)":
# "PowerEdge R730 (SKU=NotProvided;ModelName=PowerEdge R730)":
# "PowerEdge R7525 (SKU=NotProvided;ModelName=PowerEdge R7525)":
class PowerEdge(Machine):
	def __init__(self, sp):
		super().__init__(sp)
		'''
		self.inlet_temp = ["Inlet Temp", "49-Sys Exhaust 1", "01-Inlet Ambient", "Temp_Inlet_MB"]
		self.outlet_temp = ["Exhaust Temp", "50-Sys Exhaust 2", "28-LOM Card", "Temp_Outlet"]
		self.fan_speed = ["Fan1", "Fan2", "Fan3", "Fan4", "Fan5", "Fan6" ]
		'''
		self.inlet_temp = ["Inlet Temp"]
		self.outlet_temp = ["Exhaust Temp"]
		self.fan_speed = ["Fan1", "Fan2", "Fan3", "Fan4", "Fan5", "Fan6" ]
		self.bmc_cmds['sensor_reading'] = ['ipmitool', '-I', self.interface, '-c',
			'-U', self.mach['power_user'], '-P', self.mach['power_pass'],
			'-H', self.mach['power_address'], 'sensor', 'reading',
			'Fan1', 'Fan2', 'Fan3', 'Fan4', 'Fan5', 'Fan6',
			'Inlet Temp', 'Exhaust Temp']
		self.bmc_funcs.append(self.run_sensor_reading)
		self.bmc_run_window = 60 # sec

	def __del__(self):
		pass


# "DGX-1 (Default string)":
class DGX(Machine):
	def __init__(self, sp):
		super().__init__(sp)
		self.bmc_cmds['sensor_reading'] = ['ipmitool', '-I', self.interface, '-c',
			'-U', self.mach['power_user'], '-P', self.mach['power_pass'],
			'-H', self.mach['power_address'], 'sensor', 'reading',
			'Temp_Inlet_MB', 'Temp_Outlet',
			'Fan_SYS0_1', 'Fan_SYS0_2', 'Fan_SYS1_1', 'Fan_SYS1_2',
			'Fan_SYS2_1', 'Fan_SYS2_2', 'Fan_SYS3_1', 'Fan_SYS3_2',
			'Power_GPGPU0', 'Power_GPGPU1', 'Power_GPGPU2', 'Power_GPGPU3',
			'Power_GPGPU4', 'Power_GPGPU5', 'Power_GPGPU6', 'Power_GPGPU7',
			'Temp_GPGPU0', 'Temp_GPGPU1', 'Temp_GPGPU2', 'Temp_GPGPU3',
			'Temp_GPGPU4', 'Temp_GPGPU5', 'Temp_GPGPU6', 'Temp_GPGPU7']

		self.inlet_temp = ["Temp_Inlet_MB"]
		self.outlet_temp = ["Temp_Outlet"]
		self.fan_speed = ['Fan_SYS0_1', 'Fan_SYS0_2', 'Fan_SYS1_1', 'Fan_SYS1_2',
				'Fan_SYS2_1', 'Fan_SYS2_2', 'Fan_SYS3_1', 'Fan_SYS3_2']
		self.gpu_power = ['Power_GPGPU0', 'Power_GPGPU1', 'Power_GPGPU2', 'Power_GPGPU3',
				'Power_GPGPU4', 'Power_GPGPU5', 'Power_GPGPU6', 'Power_GPGPU7']
		self.gpu_temp = ['Temp_GPGPU0', 'Temp_GPGPU1', 'Temp_GPGPU2', 'Temp_GPGPU3',
				'Temp_GPGPU4', 'Temp_GPGPU5', 'Temp_GPGPU6', 'Temp_GPGPU7']
		self.bmc_funcs.append(self.run_sensor_reading)

	def __del__(self):
		pass

# "PRIMERGY RX2540 M2 (ABN:K1566-V401-2420)":
# "PRIMERGY RX2540 M2 (ABN:K1566-V401-5622)":
class RX2540(Machine):
	def __init__(self, sp):
		super().__init__(sp)
		self.bmc_cmds['sensor_reading'] = ['ipmitool', '-I', self.interface, '-c',
			'-U', self.mach['power_user'], '-P', self.mach['power_pass'],
			'-H', self.mach['power_address'], 'sensor', 'reading',
			'Systemboard 1', 'Systemboard 2',
			'FAN1 SYS', 'FAN2 SYS', 'FAN3 SYS', 'FAN4 SYS', 'FAN5 SYS',
			'CPU1 Power', 'CPU2 Power']
			#'CPU1 Power', 'CPU2 Power', 'FAN Power', 'HDD Power', 'System Power',
			#'Total Power', 'Total Power Out']
		self.inlet_temp = ["Systemboard 1"]
		self.outlet_temp = ["Systemboard 2"]
		self.fan_speed = ['FAN1 SYS', 'FAN2 SYS', 'FAN3 SYS', 'FAN4 SYS', 'FAN5 SYS']
		self.cpu_power = ['CPU1 Power', 'CPU2 Power']
		#self.fan_power = ['FAN Power']
		#self.hdd_power = ['HDD Power']
		#self.systemboard_power = ['System Power']
		#self.total_power = ['Total Power', 'Total Power Out']
		self.bmc_funcs.append(self.run_sensor_reading)
		self.bmc_run_window = 5 # sec

	def __del__(self):
		pass


# "PRIMERGY RX2530 M4 (ABN:K1592-V401-506)":
class RX2530(Machine):
	def __init__(self, sp):
		super().__init__(sp)
		self.bmc_cmds['sensor_reading'] = ['ipmitool', '-I', self.interface, '-c',
			'-U', self.mach['power_user'], '-P', self.mach['power_pass'],
			'-H', self.mach['power_address'], 'sensor', 'reading',
			'Systemboard 1', 'Systemboard 2',
			'FAN1 SYS', 'FAN2 SYS', 'FAN3 SYS', 'FAN4 SYS', 'FAN5 SYS',
			'FAN6 SYS', 'FAN7 SYS', 'FAN8 SYS',
			'Systemboard Pwr', 'Total Power', 'Total Power Out']
		self.inlet_temp = ["Systemboard 1"]
		self.outlet_temp = ["Systemboard 2"]
		self.fan_speed = ['FAN1 SYS', 'FAN2 SYS', 'FAN3 SYS', 'FAN4 SYS', 'FAN5 SYS',
				'FAN6 SYS', 'FAN7 SYS', 'FAN8 SYS']
		self.systemboard_power = ['Systemboard Pwr']
		self.total_power = ['Total Power', 'Total Power Out']
		self.bmc_funcs.append(self.run_sensor_reading)
		self.bmc_run_window = 5 # sec

	def __del__(self):
		pass

# "ProLiant DL380 Gen9 (719064-B21)"
class Proliant(Machine):
	def __init__(self, sp):
		super().__init__(sp)
		self.bmc_cmds['dcmi_power'] = ['ipmitool', '-I', self.interface, '-c',
			'-U', self.mach['power_user'], '-P', self.mach['power_pass'],
			'-H', self.mach['power_address'], 'dcmi', 'power', 'reading']
		self.bmc_funcs = [ self.run_dcmi_power_reading ]
		self.bmc_run_window = 300 # sec

	def __del__(self):
		pass

class IBMPOWER9(Machine):
	def __init__(self, sp):
		super().__init__(sp)
		self.bmc_cmds['sensor_reading'] = ['ssh',
			'%s@%s'%(self.mach['power_user'],self.mach['power_address']),
			'/tmp/bmc_fetchd', '--op query']

		self.bmc_funcs = [ self.run_sensor_reading_openbmc ]
		self.bmc_run_window = 20 # sec

	def __del__(self):
		pass

# Whenever a new system product is introduced to the under-cloud,
# Implement a new subclass of Machine and register the new subclass here.

factory = MachineFactory()
factory.register_type('PowerEdge T630 (SKU=NotProvided;ModelName=PowerEdge T630)', PowerEdge)
factory.register_type('PowerEdge R630 (SKU=NotProvided;ModelName=PowerEdge R630)', PowerEdge)
factory.register_type('PowerEdge R730 (SKU=NotProvided;ModelName=PowerEdge R730)', PowerEdge)
factory.register_type('PowerEdge R740 (SKU=NotProvided;ModelName=PowerEdge R740)', PowerEdge)
factory.register_type('PowerEdge R7525 (SKU=NotProvided;ModelName=PowerEdge R7525)', PowerEdge)

factory.register_type('DGX-1 (Default string)', DGX)

factory.register_type('PRIMERGY RX2530 M4 (ABN:K1592-V401-506)', RX2530)
factory.register_type('PRIMERGY RX2540 M2 (ABN:K1566-V401-5622)', RX2540)
factory.register_type('PRIMERGY RX2540 M2 (ABN:K1566-V401-2420)', RX2540)

factory.register_type('-[7947IDS]- (XxXxXxX)', Machine)

factory.register_type('IBMPOWER9', IBMPOWER9)

factory.register_type('ProLiant DL380 G7 (583914-B21)', Machine)
factory.register_type('ProLiant DL360p Gen8 (654081-B21)', Machine)
factory.register_type('ProLiant DL380 Gen9 (719064-B21)', Proliant)
factory.register_type('ProLiant DL380 Gen10 (868703-B21)', Proliant)
factory.register_type('ProLiant DL380 Gen10 (868706-B21)', Proliant)
factory.register_type('ProLiant XL170r Gen10 (867055-B21)', Proliant)

factory.register_type('SYS-7048GR-TR (Default string)', Machine)

#print("library test completed successfully")
