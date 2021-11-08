#!/usr/bin/env python3

#
# Copyright (C) 2018-2021 Maruthi Seshidhar Inukonda - All Rights Reserved.
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
import os
import io

sys.path.append('/usr/local/lib/python3.6/dist-packages/dhi-ojas/')
#sys.path.append('../lib/')
import my_maas_lib
import my_gnocchi_lib

def get_machines(host=True, bmc=False):

	machine_count = 0
	with open("/etc/dhi-ojas/hosts.yml", 'r') as stream:
	    hosts_config = yaml.safe_load(stream)
	hosts = list()
	if 'hosts' in hosts_config and hosts_config['hosts'] != None and len(hosts_config['hosts']) != 0:
		hosts = hosts_config['hosts']
		for h in hosts:
			machine_count += 1
			print("hostname:", h['hostname'], "status_name:", "-")

	ret = my_maas_lib.get_machines()
	mach_list = json.loads(ret)
	for mach in mach_list:
		machine_count += 1
		# Only ready/deployed machines have power_parameters and inventory
		if mach['status_name'] == "New":
			continue
		print("hostname:", mach['hostname'], "status_name:", mach['status_name'], "mach['power_state']:", mach['power_state'])
		#if mach['power_state'] != 'on':
		#	continue
		#print("hostname:", mach['hostname'], "status_name:", mach['status_name'])
		# Only deployed machines could have agent running.
		if len(args.machine_state) > 0 and mach['status_name'] not in args.machine_state:
			continue
		#print("\n")
		#print("mach:", mach)
		if len(mach['ip_addresses']) == 0:
			continue
		#print("hostname:", mach['hostname'], "status_name:", mach['status_name'])
		#print("ip_addresses:", mach['ip_addresses'])
		user = None
		rack = None
		unit = None
		if len(mach['description']) != 0:
			keyval = mach['description'].split(';')
			for kv in keyval:
				try:
					[k, v] = kv.split(':')
				except ValueError:
					print("not in key:value format. keyval:", keyval)
					continue
				if k == "user":
					user = v
				elif k == "rack":
					rack = v
				elif k == "unit":
					unit = v
		host = {'hostname': mach['hostname'],
			'ip_address': mach['ip_addresses'][0],
			'user': user,
			'power_state': mach['power_state']}

		if bmc:
			ret = my_maas_lib.get_machine_power_parameters(mach['system_id'])
			mach['power_parameters'] = json.loads(ret)
			if 'power_parameters' in mach:
				#print("power_parameters:", mach['power_parameters'])
				for k,v in mach['power_parameters'].items():
					host[k] = v

		#print(host)
		hosts.append(host)

	print("onboarded machine_count:", machine_count)
	print("len(hosts):", len(hosts))
	#print("hosts:", hosts)

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
	cmds = dict()
	login_count = dict()
	idx = 0
	for h in hosts:
		hostname = h['hostname']
		login_count[hostname] = -1
		if h['power_state'] == 'off':
			login_count[hostname] = -3
			continue
		elif h['power_state'] != 'on':
			continue
		if 'user' not in h or not h['user'] or len(h['user']) == 0:
			continue
		cmds[hostname] = ['ssh', '-o', 'StrictHostKeyChecking=no',
				'-o', 'UserKnownHostsFile=/dev/null',
				'%s@%s' %(h['user'], h['ip_address']),
				'export PATH=~/.local/bin/:$PATH; last -s -1days']
	#print("len(cmds):", len(cmds))
	#print("cmds:", cmds)

	future_hash = dict()
	future_list = list()
	for k,v in cmds.items():
		cmdref = call_cmd(*v)
		future_list.append(cmdref)
		future_hash[cmdref] = k

	# Get the async functions' results (a tuple having sets)
	results = loop.run_until_complete(asyncio.wait(future_list))
	# set#0 contains the results.
	# Iterate over each element in the set to get individual results
	for id,val in enumerate(results[0]):
		hostname = future_hash[val._coro]
		#print("id:", id, " val:", val, " hostname:", hostname)
		#print(val.result())
		if len(val.result()) == 0:
			print("last command failed on ", hostname)
			login_count[hostname] = -2
			continue
		out = val.result().splitlines()
		login_count[hostname] = 0
		for line in out:
			#print(line)
			token = line.split()
			#print("token:", token)
			if len(token) == 0:
				continue
			if 'pts' in token[1] or 'tty' in token[1]:
				login_count[hostname] += 1

	return login_count

def run_cmds_uptime(loop, hosts):
	cmds = dict()
	usage_prcnt = dict()
	idx = 0
	for h in hosts:
		hostname = h['hostname']
		usage_prcnt[hostname] = -1
		if h['power_state'] == 'off':
			usage_prcnt[hostname] = -3
			continue
		elif h['power_state'] != 'on':
			continue
		if 'user' not in h or not h['user'] or len(h['user']) == 0:
			continue
		cmds[hostname] = ['ssh', '-o', 'StrictHostKeyChecking=no',
				'-o', 'UserKnownHostsFile=/dev/null',
				'%s@%s' %(h['user'], h['ip_address']), 'uptime']

	#print("len(cmds):", len(cmds))
	#print("cmds:", cmds)

	future_hash = dict()
	future_list = list()
	for k,v in cmds.items():
		cmdref = call_cmd(*v)
		future_list.append(cmdref)
		future_hash[cmdref] = k

	# Get the async functions' results (a tuple having sets)
	results = loop.run_until_complete(asyncio.wait(future_list))
	# set#0 contains the results.
	# Iterate over each element in the set to get individual results
	for id,val in enumerate(results[0]):
		hostname = future_hash[val._coro]
		#print("id:", id, " val:", val, " hostname:", hostname, " result:", val.result())
		if len(val.result()) == 0:
			print("uptime command failed on ", hostname)
			usage_prcnt[hostname] = -2
			continue
		token = val.result().split('load average:')
		if len(token) == 0:
			print("uptime command output is empty on ", hostname)
			usage_prcnt[hostname] = -3
			continue
		usage_prcnt[hostname] = token[1].split(',')[1]
		#print("token:", token)

	return usage_prcnt

def run_cmds_ipmitool_dcmi_power_reading(loop, hosts):
	cmds = dict()
	power_reading = dict()
	idx = 0
	for h in hosts:
		hostname = h['hostname']
		power_reading[hostname] = -1
		# Only powered on systems' agent is reachable.
		if h['power_state'] == 'error':
			continue
		if ( 'power_state' not in h or 'power_pass' not in h or
		     'power_user' not in h or 'power_driver' not in h or
		     'power_address' not in h ):
			continue
		if h['power_driver'] == "LAN_2_0":
			interface = "lanplus"
		elif h['power_driver'] == "LAN":
			interface = "lan"
		cmds[hostname] = ['ipmitool', '-I', interface, '-c',
			'-U', h['power_user'], '-P', h['power_pass'],
			'-H', h['power_address'], 'dcmi', 'power', 'reading']
	#print("len(cmds):", len(cmds))
	#print("cmds:", cmds)

	future_hash = dict()
	future_list = list()
	for k,v in cmds.items():
		cmdref = call_cmd(*v)
		future_list.append(cmdref)
		future_hash[cmdref] = k

	# Get the async functions' results (a tuple having sets)
	results = loop.run_until_complete(asyncio.wait(future_list))
	# set#0 contains the results.

	# Iterate over each element in the set to get individual results
	for id,val in enumerate(results[0]):
		hostname = future_hash[val._coro]
		#print("id:", id, " val:", val, " hostname:", hostname)
		#print(val.result())
		if len(val.result()) == 0:
			print("ipmitool dcmi power reading command failed on ", hostname)
			power_reading[hostname] = -2
			continue
		if args.dump:
			# write the dcmi powerreading to files for offline analysis
			fh = open("%s/%s-ipmitool-dcmi-powerreading.txt" %(args.dumpdir, hostname), "wt")
			n = fh.write(val.result())
			fh.close()
		# get required statistics
		out = val.result().splitlines()
		#print(out)
		if len(out) != 7:
			continue
		# First line contains "Instantaneous power reading: x Watts"
		# Fourth line contains "Average power reading over sample period: x Watts"
		reading_units = out[0].split(':')[1]
		#print('reading_units:', reading_units)
		power_reading[hostname] = float(reading_units.split()[0])

	return power_reading

def run_cmds_ipmitool_fru(loop, hosts):
	cmds = dict()
	fru_listing = dict()
	idx = 0
	for h in hosts:
		hostname = h['hostname']
		fru_listing[hostname] = { 'result' : -1, 'output' : [] }
		# Only powered on systems' agent is reachable.
		if h['power_state'] == 'error':
			continue
		if ( 'power_state' not in h or 'power_pass' not in h or
		     'power_user' not in h or 'power_driver' not in h or
		     'power_address' not in h ):
			continue
		if h['power_driver'] == "LAN_2_0":
			interface = "lanplus"
		elif h['power_driver'] == "LAN":
			interface = "lan"
		cmds[hostname] = ['ipmitool', '-I', interface,
			'-U', h['power_user'], '-P', h['power_pass'],
			'-H', h['power_address'], 'fru']
	#print("len(cmds):", len(cmds))
	#print("cmds:", cmds)

	future_hash = dict()
	future_list = list()
	for k,v in cmds.items():
		cmdref = call_cmd(*v)
		future_list.append(cmdref)
		future_hash[cmdref] = k

	# Get the async functions' results (a tuple having sets)
	results = loop.run_until_complete(asyncio.wait(future_list))
	# set#0 contains the results.

	# Iterate over each element in the set to get individual results
	for id,val in enumerate(results[0]):
		hostname = future_hash[val._coro]
		#print("id:", id, " val:", val, " hostname:", hostname)
		#print(val.result())
		if len(val.result()) == 0:
			print("ipmitool fru command failed on ", hostname)
			fru_listing[hostname] = { 'result' : -2, 'output' : [] }
			continue
		if args.dump:
			# write the dcmi powerreading to files for offline analysis
			fh = open("%s/%s-ipmitool-fru.txt" %(args.dumpdir, hostname), "wt")
			n = fh.write(val.result())
			fh.close()
		# get required statistics
		out = val.result().splitlines()
		#print(out)
		# "Present FRU data"
		fru_listing[hostname] = { 'result' : 0, 'output' : out }

	return fru_listing

def run_cmds_ipmitool_sensor_list(loop, hosts):
	cmds = dict()
	sensor_listing = dict()
	idx = 0
	for h in hosts:
		hostname = h['hostname']
		sensor_listing[hostname] = { 'result' : -1, 'output' : [] }
		# Only powered on systems' agent is reachable.
		if h['power_state'] == 'error':
			continue
		if ( 'power_state' not in h or 'power_pass' not in h or
		     'power_user' not in h or 'power_driver' not in h or
		     'power_address' not in h ):
			continue
		if h['power_driver'] == "LAN_2_0":
			interface = "lanplus"
		elif h['power_driver'] == "LAN":
			interface = "lan"
		cmds[hostname] = ['ipmitool', '-I', interface,
			'-U', h['power_user'], '-P', h['power_pass'],
			'-H', h['power_address'], 'sensor', 'list']
	#print("len(cmds):", len(cmds))
	#print("cmds:", cmds)

	future_hash = dict()
	future_list = list()
	for k,v in cmds.items():
		cmdref = call_cmd(*v)
		future_list.append(cmdref)
		future_hash[cmdref] = k

	# Get the async functions' results (a tuple having sets)
	results = loop.run_until_complete(asyncio.wait(future_list))
	# set#0 contains the results.

	# Iterate over each element in the set to get individual results
	for id,val in enumerate(results[0]):
		hostname = future_hash[val._coro]
		#print("id:", id, " val:", val, " hostname:", hostname)
		#print(val.result())
		if len(val.result()) == 0:
			print("ipmitool sensor list command failed on ", hostname)
			sensor_listing[hostname] = { 'result' : -2, 'output' : [] }
			continue
		if args.dump:
			# write the dcmi powerreading to files for offline analysis
			fh = open("%s/%s-ipmitool-sensor-list.txt" %(args.dumpdir, hostname), "wt")
			n = fh.write(val.result())
			fh.close()
		# get required statistics
		out = val.result().splitlines()
		#print(out)
		# "Present Sensor data"
		sensor_listing[hostname] = { 'result' : 0, 'output' : out }

	return sensor_listing

def run_cmds_ipmitool_sdr(loop, hosts):
	cmds = dict()
	sensor_reading = dict()
	idx = 0
	for h in hosts:
		hostname = h['hostname']
		obj = {"Inlet Temp": -1, "Exhaust Temp": -1}
		sensor_reading[hostname] = obj
		# Only powered on systems' agent is reachable.
		if h['power_state'] == 'error':
			continue
		if ( 'power_state' not in h or 'power_pass' not in h or
		     'power_user' not in h or 'power_driver' not in h or
		     'power_address' not in h ):
			continue
		if h['power_driver'] == "LAN_2_0":
			interface = "lanplus"
		elif h['power_driver'] == "LAN":
			interface = "lan"
		cmds[hostname] = ['ipmitool', '-I', interface, '-c',
			'-U', h['power_user'], '-P', h['power_pass'],
			'-H', h['power_address'], 'sdr']
	#print("len(cmds):", len(cmds))
	#print("cmds:", cmds)

	future_hash = dict()
	future_list = list()
	for k,v in cmds.items():
		cmdref = call_cmd(*v)
		future_list.append(cmdref)
		future_hash[cmdref] = k

	# Get the async functions' results (a tuple having sets)
	results = loop.run_until_complete(asyncio.wait(future_list))
	# set#0 contains the results.
	inlet_header = ["Inlet Temp", "49-Sys Exhaust 1", "01-Inlet Ambient", "Temp_Inlet_MB"]
	outlet_header = ["Exhaust Temp", "50-Sys Exhaust 2", "28-LOM Card", "Temp_Outlet"]

	# Iterate over each element in the set to get individual results
	for id,val in enumerate(results[0]):
		hostname = future_hash[val._coro]
		#print("id:", id, " val:", val, " hostname:", hostname)
		#print(val.result())
		if len(val.result()) == 0:
			print("ipmitool sdr command failed on ", hostname)
			continue
		if args.dump:
			# write the sdr data to files for offline analysis
			fh = open("%s/%s-ipmitool-sdr.txt" %(args.dumpdir, hostname), "wt")
			n = fh.write(val.result())
			fh.close()
		# get required statistics
		out = val.result().splitlines()
		# other params
		obj = {"Inlet Temp": -1, "Exhaust Temp": -1}
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
		sensor_reading[hostname] = obj

	return sensor_reading

def sigint_handler(signum, frame):
	print('INT Signal handler called with signal', signum)
	sys.exit(0)

def fetch_login_count(hosts, tm):
	loop = asyncio.get_event_loop()

	# run commands on the machines asynchronously.
	login_count = run_cmds_last(loop, hosts)
	print('len(login_count):', len(login_count), 'login_count:', login_count)

	# print summary
	login_count_nonzero = 0
	login_count_zero = 0
	login_count_off = 0
	login_count_unknown = 0
	login_count_error = 0
	for k,v in login_count.items():
		if v > 0:
			login_count_nonzero += 1
		elif v == 0:
			login_count_zero += 1
		elif v == -1:
			login_count_unknown += 1
		elif v == -3:
			login_count_off += 1
		elif v == -2:
			login_count_error += 1
	print('#nonzero:', login_count_nonzero)
	print('#zero:', login_count_zero)
	print('#off:', login_count_off)
	print('#unknown:', login_count_unknown)
	print('#error:', login_count_error)

	resource_measures = []
	# Iterate over the results and create a parameter hash
	for i in range(0, len(hosts)):
		hostname = hosts[i]['hostname']
		resource_measures.append({
			'resource_key' : hostname,
			'measures' : [
				{ 'time': tm, 'type' : 'login_count', 'value' : login_count[hostname] }
			]
		})

	if not args.nostore :
		my_gnocchi_lib.save_in_gnocchi("fetchd", resource_measures)

	loop.close()

def fetch_load_avg(hosts, tm):
	loop = asyncio.get_event_loop()

	# run commands on the machines asynchronously.
	loadavg_prcnt = run_cmds_uptime(loop, hosts)
	print('len(loadavg_prcnt):', len(loadavg_prcnt), 'loadavg_prcnt:', loadavg_prcnt)

	# print summary
	loadavg_prcnt_nonzero = 0
	loadavg_prcnt_zero = 0
	loadavg_prcnt_off = 0
	loadavg_prcnt_unknown = 0
	loadavg_prcnt_error = 0
	for k,v in loadavg_prcnt.items():
		vf = float(v)
		if vf > 0:
			loadavg_prcnt_nonzero += 1
		elif vf == 0:
			loadavg_prcnt_zero += 1
		elif vf == -1:
			loadavg_prcnt_unknown += 1
		elif vf == -3:
			loadavg_prcnt_off += 1
		elif vf == -2:
			loadavg_prcnt_error += 1
	print('#nonzero:', loadavg_prcnt_nonzero)
	print('#zero:', loadavg_prcnt_zero)
	print('#off:', loadavg_prcnt_off)
	print('#unknown:', loadavg_prcnt_unknown)
	print('#error:', loadavg_prcnt_error)

	resource_measures = []
	# Iterate over the results and create a parameter hash
	for i in range(0, len(hosts)):
		hostname = hosts[i]['hostname']
		resource_measures.append({
			'resource_key' : hostname,
			'measures' : [
				{ 'time': tm, 'type' : 'load_avg', 'value' : loadavg_prcnt[hostname] }
			]
		})

	if not args.nostore :
		my_gnocchi_lib.save_in_gnocchi("fetchd", resource_measures)

	loop.close()

def fetch_bmc_data(hosts, tm):
	loop = asyncio.get_event_loop()

	# run commands on the machines asynchronously.
	power_readings = run_cmds_ipmitool_dcmi_power_reading(loop, hosts)
	print('len(power_readings):', len(power_readings), 'power_readings:', power_readings)

	machine_count = 0
	machine_unknown_count = 0
	machine_up_count = 0
	machine_down_count = 0
	machine_error_count = 0
	pwr_sum = 0
	resource_measures = []
	# Iterate over the results and create a parameter hash
	for i in range(0, len(hosts)):
		hostname = hosts[i]['hostname']
		machine_count += 1
		if hosts[i]['power_state'] == "error":
			machine_unknown_count += 1
			up = -1
		elif hosts[i]['power_state'] == "on":
			machine_up_count += 1
			up = 1
		elif hosts[i]['power_state'] == "off":
			machine_down_count += 1
			up = 0
		else:
			print(hostname, ": power_state:", hosts[i]['power_state'])
			machine_error_count += 1
			up = -2
		if power_readings[hostname] > 0:
			pwr_sum += power_readings[hostname]
		resource_measures.append({
			'resource_key' : hostname,
			'measures' : [
				{ 'time': tm, 'type' : 'Pwr Consumption', 'value' : power_readings[hostname] },
				{ 'time': tm, 'type' : 'up', 'value' : up },
			]
		})

	if not args.nostore :
		my_gnocchi_lib.save_in_gnocchi("fetchd", resource_measures)
	print("pwr_sum:", pwr_sum)
	print("machine_count:", machine_count)
	print("machine_unknown_count:", machine_unknown_count)
	print("machine_up_count:", machine_up_count)
	print("machine_down_count:", machine_down_count)
	print("machine_error_count:", machine_error_count)

	resource_measures = []
	# add machine_count and power_consump_sum as resource
	resource_measures.append({
		'resource_key' : "total_machines",  # using machine header for the sake of generality
		'measures' : [
			{ 'time': tm, 'type' : 'machine_unknown_count', 'value' : machine_unknown_count },
			{ 'time': tm, 'type' : 'machine_error_count', 'value' : machine_error_count },
			{ 'time': tm, 'type' : 'machine_down_count', 'value' : machine_down_count },
			{ 'time': tm, 'type' : 'machine_up_count', 'value' : machine_up_count },
			{ 'time': tm, 'type' : 'machine_count', 'value' : machine_count },
			{ 'time': tm, 'type' : 'pwr_sum', 'value' : pwr_sum },
		]
	})
	if not args.nostore :
		my_gnocchi_lib.save_in_gnocchi("fetchd", resource_measures)

	resource_measures = []
	# run commands on the machines asynchronously.
	sensor_readings = run_cmds_ipmitool_sdr(loop, hosts)
	print('len(sensor_readings):', len(sensor_readings), 'sensor_readings:', sensor_readings)

	# Iterate over the results and create a parameter hash
	for i in range(0, len(hosts)):
		hostname = hosts[i]['hostname']
		resource_measures.append({
			'resource_key' : hostname,
			'measures' : [
				{ 'time': tm, 'type' : 'Inlet Temp', 'value' : sensor_readings[hostname]['Inlet Temp'] },
				{ 'time': tm, 'type' : 'Exhaust Temp', 'value' : sensor_readings[hostname]['Exhaust Temp'] }
			]
		})

	if not args.nostore :
		my_gnocchi_lib.save_in_gnocchi("fetchd", resource_measures)

	# run commands on the machines asynchronously.
	fru_listings = run_cmds_ipmitool_fru(loop, hosts)
	#print('len(fru_listings):', len(fru_listings))
	print('len(fru_listings):', len(fru_listings),
		'fru_listings:', [(k,v['result'],len(v['output'])) for k,v in fru_listings.items()])

	# run commands on the machines asynchronously.
	sensor_listings = run_cmds_ipmitool_sensor_list(loop, hosts)
	#print('len(sensor_listings):', len(sensor_listings))
	print('len(sensor_listings):', len(sensor_listings),
		'sensor_listings:', [(k,v['result'],len(v['output'])) for k,v in sensor_listings.items()])

	loop.close()

if __name__ == "__main__":
	# Parse the command line arguments
	parser = argparse.ArgumentParser(description='proxy agent to fetch statistics via inband')
	parser.add_argument('--dumpdir', default="logs/xxxx", help='directory to save unprocessed fetched data')
	parser.add_argument('--dump', default=False, action='store_true', help='dump unprocessed fetched data')
	parser.add_argument('--nostore', default=False, action='store_true', help='nostore')
	parser.add_argument('--load_avg', default=False, action='store_true', help='load_avg')
	parser.add_argument('--login_count', default=False, action='store_true', help='login_count')
	parser.add_argument('--bmc_data', default=False, action='store_true', help='bmc_data')
	parser.add_argument('--machine_state', default=[], nargs='+', help='machine_state <val>')

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
	h = True
	if args.bmc_data:
		b = True
	else:
		b = False
	hosts = get_machines(h, b)
	if len(hosts) == 0:
		sys.exit(0)

	if args.dump:
		os.makedirs(args.dumpdir, exist_ok=True)
		for h in hosts:
			hostname = h['hostname']
			# write the sdr data to files for offline analysis
			fh = open("%s/%s-host.txt" %(args.dumpdir, hostname), "wt")
			mh = h.copy()
			mh['power_pass'] = "xxxx"
			json.dump(mh, fh, indent=4)
			fh.close()

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
