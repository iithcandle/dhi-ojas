#!/usr/bin/env python3

#
# Copyright (C) 2018-2019 Maruthi Seshidhar Inukonda - All Rights Reserved.
# maruthi.inukonda@gmail.com
#
# This file is released under the Affero GPLv3 License.
#

import argparse
import json
import string
import time
from datetime import datetime, timedelta
import pytz
import subprocess
import pprint
import asyncio
import signal
import sys
import time
from gnocchiclient import auth, exceptions
from gnocchiclient.v1 import client, metric
import threading
import multiprocessing
import yaml
import io

sys.path.append('/usr/local/lib/python3.6/dist-packages/dhi-ojas/')
import my_maas_lib
import my_gnocchi_lib

def get_machines(host=True, bmc=False):

	machine_count = 0
	with open("/etc/dhi-ojas/hosts.yml", 'r') as stream:
	    hosts_config = yaml.safe_load(stream)
	hosts = list()
	if 'hosts' in hosts_config and hosts_config['hosts'] != None and len(hosts_config['hosts']) != 0:
		hosts = hosts_config['hosts']
		for host in hosts:
			machine_count += 1
			print("hostname:", host['hostname'], "status_name:", "-")

	mach_list = my_maas_lib.get_machines(host, bmc)
	for mach in mach_list:
		machine_count += 1
		# Only powered on systems' agent is reachable.
		if mach['power_state'] == 'error':
			continue
		print("hostname:", mach['hostname'], "status_name:", mach['status_name'], "mach['power_state']:", mach['power_state'])
		#if mach['power_state'] != 'on':
		#	continue
		#print("hostname:", mach['hostname'], "status_name:", mach['status_name'])
		# Only deployed machines could have agent running.
		#if mach['status_name'] not in args.machine_state:
		#	continue
		#print("\n")
		#print("mach:", mach)
		if len(mach['ip_addresses']) == 0:
			continue
		#print("hostname:", mach['hostname'], "status_name:", mach['status_name'])
		#print("ip_addresses:", mach['ip_addresses'])
		if len(mach['description']) != 0:
			user = mach['description'].split(':')[1]
		else:
			user = ""
		host = {'hostname': mach['hostname'],
			'ip_address': mach['ip_addresses'][0],
			'user': user,
			'power_state': mach['power_state']}
		if 'power_parameters' in mach:
			#print("power_parameters:", mach['power_parameters'])
			for k,v in mach['power_parameters'].items():
				host[k] = v
		#print(host)
		hosts.append(host)

	print("machine_count:", machine_count)

	return hosts

async def call_cmd(*cmd):
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
		print(
			"Failed:", *cmd, "pid=%s, result: %s"
			%(process.pid, stderr.decode().strip()),
			flush=True,
		)

	# Result
	result = stdout.decode().strip()

	# Return stdout
	return result

def run_cmds_last(loop, hosts):
	cmds = []
	#print("hosts:", hosts)
	for h in hosts:
		cmds.append(['ssh', '-o', 'StrictHostKeyChecking=no',
			'-o', 'UserKnownHostsFile=/dev/null',
			'%s@%s' %(h['user'], h['ip_address']), 'export PATH=~/.local/bin/:$PATH; last -s -1days'])

	futures = [call_cmd(*cmd) for cmd in cmds]
	# Get the async functions' results (a tuple having sets)
	results = loop.run_until_complete(asyncio.wait(futures))
	#login_count = list(range(0, len(results[0])))
	# set#0 contains the results.
	login_count = [0] * len(results[0])
	# Iterate over each element in the set to get individual results
	for k in range(0, len(futures)):
		cmd = futures[k]
		for id,val in enumerate(results[0]):
			if val._coro == cmd:
				#print("found id:", id, " val:", val)
				#print(val.result())
				out = val.result().splitlines()
				for line in out:
					#print(line)
					token = line.split()
					#print("token:", token)
					if len(token) == 0:
						continue
					if 'pts' in token[1] or 'tty' in token[1]:
						login_count[k] += 1
				break
	return login_count

def run_cmds_uptime(loop, hosts):
	cmds = []
	#print("hosts:", hosts)
	for h in hosts:
		cmds.append(['ssh', '-o', 'StrictHostKeyChecking=no',
			'-o', 'UserKnownHostsFile=/dev/null',
			'%s@%s' %(h['user'], h['ip_address']), 'uptime'])

	futures = [call_cmd(*cmd) for cmd in cmds]
	# Get the async functions' results (a tuple having sets)
	results = loop.run_until_complete(asyncio.wait(futures))
	#usage_prcnt = list(range(0, len(results[0])))
	# set#0 contains the results.
	usage_prcnt = [0] * len(results[0])
	# Iterate over each element in the set to get individual results
	for k in range(0, len(futures)):
		cmd = futures[k]
		for id,val in enumerate(results[0]):
			if val._coro == cmd:
				#print("found id:", id, " val:", val)
				#print(val.result())
				token = val.result().split('load average:')
				if len(token) != 0:
					usage_prcnt[k] = token[1].split(',')[1]
					#print('usage_prcnt', usage_prcnt[k])
				#print("token:", token)
				break
	return usage_prcnt

def run_cmds_ipmitool_dcmi_power_reading(loop, hosts):
	cmds = []
	#print("hosts:", hosts)
	for h in hosts:
		if h['power_driver'] == "LAN_2_0":
			interface = "lanplus"
		elif h['power_driver'] == "LAN":
			interface = "lan"
		cmds.append(['ipmitool', '-I', interface, '-c',
			'-U', h['power_user'], '-P', h['power_pass'],
			'-H', h['power_address'], 'dcmi', 'power', 'reading'])

	futures = [call_cmd(*cmd) for cmd in cmds]
	# Get the async functions' results (a tuple having sets)
	results = loop.run_until_complete(asyncio.wait(futures))
	#usage_prcnt = list(range(0, len(results[0])))
	# set#0 contains the results.
	power_reading = [0] * len(results[0])

	# Iterate over each element in the set to get individual results
	for k in range(0, len(futures)):
		cmd = futures[k]
		for id,val in enumerate(results[0]):
			if val._coro == cmd:
				#print("found id:", id, " val:", val)
				#print(val.result())
				# get required statistics
				out = val.result().splitlines()
				#print(out)
				if len(out) != 7:
					continue
				# First line contains "Instantaneous power reading: x Watts"
				# Fourth line contains "Average power reading over sample period: x Watts"
				reading_units = out[0].split(':')[1]
				#print('reading_units:', reading_units)
				power_reading[k] = float(reading_units.split()[0])
				break
	return power_reading

def run_cmds_ipmitool_sdr(loop, hosts):
	cmds = []
	#print("hosts:", hosts)
	for h in hosts:
		if h['power_driver'] == "LAN_2_0":
			interface = "lanplus"
		elif h['power_driver'] == "LAN":
			interface = "lan"
		cmds.append(['ipmitool', '-I', interface, '-c',
			'-U', h['power_user'], '-P', h['power_pass'],
			'-H', h['power_address'], 'sdr'])

	futures = [call_cmd(*cmd) for cmd in cmds]
	# Get the async functions' results (a tuple having sets)
	results = loop.run_until_complete(asyncio.wait(futures))
	#usage_prcnt = list(range(0, len(results[0])))
	# set#0 contains the results.
	sensor_reading = [0] * len(results[0])
	inlet_header = ["Inlet Temp", "49-Sys Exhaust 1", "01-Inlet Ambient", "Temp_Inlet_MB"]
	outlet_header = ["Exhaust Temp", "50-Sys Exhaust 2", "28-LOM Card", "Temp_Outlet"]

	# Iterate over each element in the set to get individual results
	for k in range(0, len(futures)):
		cmd = futures[k]
		for id,val in enumerate(results[0]):
			if val._coro == cmd:
				#print("found id:", id, " val:", val)
				#print(val.result())
				# get required statistics
				out = val.result().splitlines()
				# other params
				obj = {"Inlet Temp": 0, "Exhaust Temp": 0}
				for sensor in out:
					sensor = sensor.split(',')
					if (sensor[0] in inlet_header):
						#valid sensor value
						if (str(sensor[3]) == "ok"):
							obj["Inlet Temp"] = float(sensor[1])
					elif (sensor[0] in outlet_header):
						#valid sensor value
						if (str(sensor[3]) == "ok"):
							obj["Exhaust Temp"] = float(sensor[1])
					# obj["unit"] = sensor[2]
				#print(obj)
				sensor_reading[k] = obj
				break
	return sensor_reading

def sigint_handler(signum, frame):
	print('INT Signal handler called with signal', signum)
	sys.exit(0)

def fetch_login_count(hosts, tm):
	loop = asyncio.get_event_loop()

	# run commands on the machines asynchronously.
	login_count = run_cmds_last(loop, hosts)
	print('login_count:', login_count)

	resource_measures = []
	# Iterate over the results and create a parameter hash
	for i in range(0, len(hosts)):
		resource_measures.append({
			'resource_key' : hosts[i]['hostname'],
			'measures' : [
				{ 'time': tm, 'type' : 'login_count', 'value' : login_count[i] }
			]
		})

	my_gnocchi_lib.save_in_gnocchi("fetchd", resource_measures)

	loop.close()

def fetch_load_avg(hosts, tm):
	loop = asyncio.get_event_loop()

	# run commands on the machines asynchronously.
	loadavg_prcnt = run_cmds_uptime(loop, hosts)
	print('loadavg_prcnt:', loadavg_prcnt)

	resource_measures = []
	# Iterate over the results and create a parameter hash
	for i in range(0, len(hosts)):
		resource_measures.append({
			'resource_key' : hosts[i]['hostname'],
			'measures' : [
				{ 'time': tm, 'type' : 'load_avg', 'value' : loadavg_prcnt[i] }
			]
		})

	my_gnocchi_lib.save_in_gnocchi("fetchd", resource_measures)

	loop.close()

def fetch_bmc_data(hosts, tm):
	loop = asyncio.get_event_loop()

	# run commands on the machines asynchronously.
	power_readings = run_cmds_ipmitool_dcmi_power_reading(loop, hosts)
	print('power_readings:', power_readings)

	machine_count = 0
	pwr_sum = 0
	resource_measures = []
	# Iterate over the results and create a parameter hash
	for i in range(0, len(hosts)):
		machine_count += 1
		pwr_sum += power_readings[i]
		if (hosts[i]['power_state'] == "on"):
			up = 1
		else:
			up = 0
		resource_measures.append({
			'resource_key' : hosts[i]['hostname'],
			'measures' : [
				{ 'time': tm, 'type' : 'Pwr Consumption', 'value' : power_readings[i] },
				{ 'time': tm, 'type' : 'up', 'value' : up },
			]
		})

	my_gnocchi_lib.save_in_gnocchi("fetchd", resource_measures)
	print("pwr_sum:", pwr_sum)

	'''
	resource_measures = []
	# add machine_count and power_consump_sum as resource
	resource_measures.append({
		'resource_key' : "total_machines",  # using machine header for the sake of generality
		'measures' : [
			{ 'time': tm, 'type' : 'machine_count', 'value' : machine_count },
			{ 'time': tm, 'type' : 'pwr_sum', 'value' : pwr_sum },
		]
	})
	my_gnocchi_lib.save_in_gnocchi("fetchd", resource_measures)
	'''

	resource_measures = []
	# run commands on the machines asynchronously.
	sensor_readings = run_cmds_ipmitool_sdr(loop, hosts)
	print('sensor_readings:', sensor_readings)

	# Iterate over the results and create a parameter hash
	for i in range(0, len(hosts)):
		resource_measures.append({
			'resource_key' : hosts[i]['hostname'],
			'measures' : [
				{ 'time': tm, 'type' : 'Inlet Temp', 'value' : sensor_readings[i]['Inlet Temp'] },
				{ 'time': tm, 'type' : 'Exhaust Temp', 'value' : sensor_readings[i]['Exhaust Temp'] }
			]
		})

	my_gnocchi_lib.save_in_gnocchi("fetchd", resource_measures)

	loop.close()

if __name__ == "__main__":
	# Parse the command line arguments
	parser = argparse.ArgumentParser(description='proxy agent to fetch statistics via inband')
	parser.add_argument('--load_avg', default=False, action='store_true', help='load_avg')
	parser.add_argument('--login_count', default=False, action='store_true', help='login_count')
	parser.add_argument('--bmc_data', default=False, action='store_true', help='bmc_data')
	parser.add_argument('--machine_state', default='[Deployed]', nargs='+', help='machine_state <val>')

	args = parser.parse_args()
	#print(args)

	# Plant a signal handler for Ctrl+C
	signal.signal(signal.SIGINT, sigint_handler)

	# get the values
	ts = time.time()
	utc_dt = datetime.utcfromtimestamp(ts)
	aware_utc_dt = utc_dt.replace(tzinfo=pytz.utc)
	tm = aware_utc_dt.strftime('%Y-%m-%d %H:%M:%S')

	# get the list of machines from maas.
	hosts = get_machines(True, True)
	if len(hosts) == 0:
		sys.exit(0)

	# Create separate process for fetching bmcdata, total, logincount and loadavg
	# threads dont work, as asyncio has per-process global data structures.
	if args.login_count :
		logincnt_job = multiprocessing.Process(target = fetch_login_count, args = (hosts, tm,), daemon=True)
	if args.load_avg :
		loadavg_job = multiprocessing.Process(target = fetch_load_avg, args = (hosts, tm,), daemon=True)
	if args.bmc_data :
		bmcdata_job = multiprocessing.Process(target = fetch_bmc_data, args = (hosts, tm,), daemon=True)

	# start the child processes
	if args.login_count :
		logincnt_job.start()
	if args.load_avg :
		loadavg_job.start()
	if args.bmc_data :
		bmcdata_job.start()

	# wait for the children to join back
	if args.login_count :
		logincnt_job.join()
	if args.load_avg :
		loadavg_job.join()
	if args.bmc_data :
		bmcdata_job.join()

	sys.exit(0)
