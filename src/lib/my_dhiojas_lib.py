#!/usr/bin/env python3

#
# Copyright (C) 2018-2022 Maruthi Seshidhar Inukonda - All Rights Reserved.
# maruthi.inukonda@gmail.com
#
# This file is released under the Affero GPLv3 License.
#
import sys
import pytz
import time
from datetime import datetime,timedelta,timezone
import json
import pprint
import multiprocessing
import subprocess
import random
import glob
import math

import os
import signal
import io
import json
import yaml
import xml.etree.ElementTree as ET
import xmltodict
import re
from collections import defaultdict
from dateutil.parser import parse
import asyncio
import pandas as pd
import numpy as np
import pickle
from sklearn.neighbors import KNeighborsClassifier
from sklearn.neighbors import KNeighborsRegressor
from sklearn import metrics
import seaborn as sns
from matplotlib import pyplot as plt
#from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn import tree
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score
from statistics import median
from sklearn.naive_bayes import GaussianNB
from sklearn.svm import SVR
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LinearRegression
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_squared_error, mean_absolute_error
def sigint_handler(signum, frame):
	print('INT Signal handler called with signal', signum)
	global queue
	global shutdown
	print('Please wait for graceful shutdown...', signum)
	shutdown.set()
	queue.put(True)
	#sys.exit(0)

def download_maas_inventory_data(outdir):
	sys.path.append('../lib/')
	sys.path.append('/usr/local/lib/python3.6/dist-packages/dhi-ojas/')
	import my_maas_lib

	machines = []
	# Iterate over maas machines and create a hash indexed by hostname.
	ret = my_maas_lib.get_machines()
	machines = json.loads(ret)
	print("machines in maas:", len(machines))

	machines_list = list()
	machines_hash = dict()
	# Collect features in a file.
	for mach in machines:
		#print("mach:", mach)
		hostname = mach['hostname']
		print("hostname:", hostname, "status_name:", mach['status_name'])
		#pprint.pprint(mach, indent=4)

		if 'virtual' in mach['tag_names']:
			continue

		# Only ready/allocated/deployed machines have inventory and hence timeseries data.
		if mach['status_name'] == "New" or mach['status_name'] == "Failed commissioning" or mach['status_name'] == "Commissioning":
			continue

		#if mach['power_state'] != 'on':
		#	continue
		#print("hostname:", mach['hostname'], "status_name:", mach['status_name'])
		#print("\n")
		#print("mach:", mach)

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
		m = {'hostname': mach['hostname'],
			'ip_address': mach['ip_addresses'][0],
			'user': user,
			'power_state': mach['power_state']}

		power_params = my_maas_lib.get_machine_power_parameters(mach['system_id'])
		'''
		mach['power_parameters'] = json.loads(power_params)
		if 'power_parameters' in mach:
			#print("power_parameters:", mach['power_parameters'])
			for k,v in mach['power_parameters'].items():
				m[k] = v
		'''
		fh = open("%s/%s-power_parameters.json" %(outdir, hostname), "wt")
		n = fh.write(power_params)
		fh.close()

		fh = open("%s/%s-machine.json" %(outdir, hostname), "wt")
		json.dump(mach, fh, indent=4, sort_keys=True)
		fh.close()

		details = my_maas_lib.get_machine_details(mach['system_id'])
		fh = open("%s/%s-details.xml" %(outdir, hostname), "wt")
		n = fh.write(details)
		fh.close()

		if hostname not in machines_list:
			machines_list.append(hostname)
			machines_hash[hostname] = m

	return machines_list, machines_hash

def download_unmanaged_inventory_data(outdir):
	import yaml

	machines_list = list()
	machines_hash = dict()

	with open("/etc/dhi-ojas/machines_nonmaas.yml", 'r') as stream:
	    machines_config = yaml.safe_load(stream)

	if 'machines' not in machines_config or machines_config['machines'] == None or len(machines_config['machines']) == 0:
		return machines_list, machines_hash

	machines = list()
	machines = machines_config['machines']
	print("machines not in maas:", len(machines))
	for h in machines:
		hostname = h['hostname']
		print("hostname:", hostname, "status_name:", "-")

		user = None
		rack = None
		unit = None
		m = {'hostname': hostname,
			'ip_address': h['ip_address'],
			'user': user,
			'power_state': h['power_state'],
			'power_user': h['power_user'],
			'power_pass': h['power_pass'],
			'power_driver': h['power_driver'],
			'power_address': h['power_address']
		}

		if hostname not in machines_list:
			machines_list.append(hostname)
			machines_hash[hostname] = m

	return machines_list, machines_hash

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


def run_cmds_ipmitool_fru(outdir, loop, machines):
	cmds = dict()
	fru_listing = dict()
	idx = 0
	for k,v in machines.items():
		hostname = v['hostname']
		fru_listing[hostname] = { 'result' : -1, 'output' : [] }
		# Only powered on systems' agent is reachable.
		if v['power_state'] == 'error':
			continue
		if ( 'power_state' not in v or 'power_pass' not in v or
		     'power_user' not in v or 'power_driver' not in v or
		     'power_address' not in v ):
			continue
		if v['power_driver'] == "LAN_2_0":
			interface = "lanplus"
		elif v['power_driver'] == "LAN":
			interface = "lan"
		cmds[hostname] = ['ipmitool', '-I', interface,
			'-U', v['power_user'], '-P', v['power_pass'],
			'-H', v['power_address'], 'fru']
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
		# write the dcmi powerreading to files for offline analysis
		fh = open("%s/%s-ipmitool-fru.txt" %(outdir, hostname), "wt")
		n = fh.write(val.result())
		fh.close()
		# get required statistics
		out = val.result().splitlines()
		#print(out)
		# "Present FRU data"
		fru_listing[hostname] = { 'result' : 0, 'output' : out }

	return fru_listing

def run_cmds_ipmitool_sensor_list(outdir, loop, machines):
	cmds = dict()
	sensor_listing = dict()
	idx = 0
	for k,v in machines.items():
		hostname = v['hostname']
		sensor_listing[hostname] = { 'result' : -1, 'output' : [] }
		# Only powered on systems' agent is reachable.
		if v['power_state'] == 'error':
			continue
		if ( 'power_state' not in v or 'power_pass' not in v or
		     'power_user' not in v or 'power_driver' not in v or
		     'power_address' not in v ):
			continue
		if v['power_driver'] == "LAN_2_0":
			interface = "lanplus"
		elif v['power_driver'] == "LAN":
			interface = "lan"
		cmds[hostname] = ['ipmitool', '-I', interface,
			'-U', v['power_user'], '-P', v['power_pass'],
			'-H', v['power_address'], 'sensor', 'list']
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
		# write the dcmi powerreading to files for offline analysis
		fh = open("%s/%s-ipmitool-sensor-list.txt" %(outdir, hostname), "wt")
		n = fh.write(val.result())
		fh.close()
		# get required statistics
		out = val.result().splitlines()
		#print(out)
		# "Present Sensor data"
		sensor_listing[hostname] = { 'result' : 0, 'output' : out }

	return sensor_listing

def download_bmc_inventory_data(machines, outdir):

	loop = asyncio.get_event_loop()

	# run commands on the machines asynchronously.
	fru_listings = run_cmds_ipmitool_fru(outdir, loop, machines)
	#print('len(fru_listings):', len(fru_listings))
	print('len(fru_listings):', len(fru_listings),
		'fru_listings:', [(k,v['result'],len(v['output'])) for k,v in fru_listings.items()])

	# run commands on the machines asynchronously.
	sensor_listings = run_cmds_ipmitool_sensor_list(outdir, loop, machines)
	#print('len(sensor_listings):', len(sensor_listings))
	print('len(sensor_listings):', len(sensor_listings),
		'sensor_listings:', [(k,v['result'],len(v['output'])) for k,v in sensor_listings.items()])

	loop.close()

def download_inventory_data(outdir):
	#l1, h1 = list(), dict()
	l1, h1 = download_maas_inventory_data(outdir)
	l2, h2 = download_unmanaged_inventory_data(outdir)

	machines_list = l1 + l2
	print("len(machines_list):", len(machines_list))

	machines_hash = h1
	machines_hash.update(h2)
	print("len(machines_hash):", len(machines_hash))
	#print("machines_hash:", machines_hash)

	download_bmc_inventory_data(machines_hash, outdir)

	fh = open("%s/machines.json" %(outdir), "wt")
	json.dump(machines_list, fh, indent=4)
	fh.close()

def curate_inventory_data(machines_list, indir, outdir, compat):
	global total_cpu_mflops
	global total_gpu_mflops

	total_cpu_mflops = 0
	total_gpu_mflops = 0
	machines = list()
	# Read features from downloaded data.
	for hostname in machines_list:
		mach_file = os.path.join(indir, "%s-machine.json" %(hostname))
		if not os.path.isfile(mach_file):
			continue
		ifh = open(mach_file, "rt")
		mach = json.load(ifh)
		ifh.close()
		#print("mach:", mach)
		#if not (hostname == "l1055-dgx1" or hostname == "candle01"):
		#	continue

		#print("===============================")
		#if os.path.isfile("%s/%s-details-lldp.xml" %(outdir, hostname)) and \
		#	os.path.isfile("%s/%s-details-lshw.xml" %(outdir, hostname)):
		#	curated_mach = curate_static_features(mach, indir, outdir, compat)
		#	if hostname not in machines:
		#		machines.append(hostname)
		#	continue

		#print("hostname:", hostname, "status_name:", mach['status_name'])
		# Only ready/allocated/deployed machines have inventory and hence timeseries data.
		if mach['status_name'] == "New" or mach['status_name'] == "Failed commissioning":
			continue

		fh = open("%s/%s-details.xml" %(indir, hostname), "rt")
		details = fh.read()
		fh.close()

		# Only successfully commissioned machines have machine details available.
		#details = { "lldp": "", "lshw": "" }
		mach_details = { "lldp": "", "lshw": "" }
		pattern = r'((<lldp)|(<list))'
		matches = re.finditer(pattern, details, re.DOTALL)
		for match in matches:
			s = match.start()
			e = match.end()
			if details[s:e] == "<lldp":
				lldp_start = match.start()
			elif details[s:e] == "<list":
				lshw_start = match.start()
			#print('finditer: Found "%s" at %d:%d' % (pattern, s, e))

		pattern = r'((<\?xml)+)'
		matches = re.finditer(pattern, details, re.DOTALL)
		xml_start_vec = [x.start() for x in matches]
		if lldp_start < lshw_start:
			lldp_start = min(xml_start_vec)
			lshw_start = max(xml_start_vec)
		else:
			lshw_start = min(xml_start_vec)
			lldp_start = max(xml_start_vec)
		#print("lldp_start:", lldp_start, " lshw_start:", lshw_start)

		if lldp_start < lshw_start: # If lldp doc is placed first
			pattern = r'(</lldp>)'
			#print(details[lldp_start:lshw_start])
			matches = re.finditer(pattern, details[lldp_start:lshw_start], re.DOTALL)
			lldp_end_vec = [x.end() for x in matches]
			#print("lldp_end_vec:", lldp_end_vec)
			if len(lldp_end_vec) > 0:
				lldp_end = lldp_start + lldp_end_vec[0]
			else: # If there is no end tag. IOW, a singleton tag.
				pattern = r'(/>)'
				matches = re.finditer(pattern, details[lldp_start:lshw_start])
				lldp_end_vec = [x.end() for x in matches]
				#print("lldp_end_vec:", lldp_end_vec)
				lldp_end = lldp_start + lldp_end_vec[-1]

			pattern = r'(</list>)'
			matches = re.finditer(pattern, details[lshw_start:], re.DOTALL)
			lshw_end_vec = [x.end() for x in matches]
			#print("lshw_end_vec:", lshw_end_vec)
			if len(lshw_end_vec) > 0:
				lshw_end = lshw_start + lshw_end_vec[0]
			else:
				pattern = r'(/>)'
				matches = re.finditer(pattern, details[lshw_start:], re.DOTALL)
				lshw_end_vec = [x.end() for x in matches]
				print("lshw_end_vec:", lshw_end_vec)
				lshw_end = lshw_start + lshw_end_vec[-1]
		else: # If lshw doc is placed first
			pattern = r'(</list>)'
			#print(details[lshw_start:lldp_start])
			matches = re.finditer(pattern, details[lshw_start:lldp_start], re.DOTALL)
			lshw_end_vec = [x.end() for x in matches]
			#print("lshw_end_vec:", lshw_end_vec)
			if len(lshw_end_vec) > 0:
				lshw_end = lshw_start + lshw_end_vec[0]
			else: # If there is no end tag. IOW, a singleton tag.
				pattern = r'(/>)'
				matches = re.finditer(pattern, details[lshw_start:lldp_start])
				lshw_end_vec = [x.end() for x in matches]
				#print("lshw_end_vec:", lshw_end_vec)
				lshw_end = lshw_start + lshw_end_vec[-1]

			pattern = r'(</lldp>)'
			matches = re.finditer(pattern, details[lldp_start:], re.DOTALL)
			lldp_end_vec = [x.end() for x in matches]
			#print("lldp_end_vec:", lldp_end_vec)
			if len(lldp_end_vec) > 0:
				lldp_end = lldp_start + lldp_end_vec[0]
			else:
				pattern = r'(/>)'
				matches = re.finditer(pattern, details[lldp_start:], re.DOTALL)
				lldp_end_vec = [x.end() for x in matches]
				print("lldp_end_vec:", lldp_end_vec)
				lldp_end = lldp_start + lldp_end_vec[-1]

		#print("lldp_end:", lldp_end, " lshw_end:", lshw_end)

		try:
			fh = open("%s/%s-details-lldp.xml" %(outdir, hostname), "wt")
			fh.write(details[lldp_start:lldp_end])
			fh.close()
		except:
			print("error opening lldp file for ", hostname)

		try:
			fh = open("%s/%s-details-lshw.xml" %(outdir, hostname), "wt")
			fh.write(details[lshw_start:lshw_end])
			fh.close()
		except:
			print("error opening lshw file for ", hostname)
			break

		if hostname not in machines:
			machines.append(hostname)

		'''
		# Load data from previous week, if any
		mach_prev = None
		if dircumulated:
			mach_file = os.path.join(args.dircumulated, "%s-machine.json" %(hostname))
			if os.path.isfile(mach_file):
				ifh = open(mach_file, "rt")
				mach_prev = json.load(ifh)
				ifh.close()
		'''

		curated_mach = curate_static_features(mach, indir, outdir, compat)

		fh = open("%s/%s-machine.json" %(outdir, hostname), "wt")
		json.dump(curated_mach, fh, indent=4, sort_keys=True)
		fh.close()

		'''
		# Save machine data for using it next week
		if args.dircumulated:
			# If H/W parts changed from last week, dont use dynamic data.
			if mach_prev and curated_mach == mach_prev:
				compat[hostname] = True
			else:
				compat[hostname] = False
				print(hostname, " previous H/W parts didnt exist or changed from data collection")

			mach_file = os.path.join(args.dircumulated, "%s-machine.json" %(hostname))
			#print("mach_file:", mach_file)
			ofh = open(mach_file, "wt")
			json.dump(curated_mach, ofh, indent=4, sort_keys=True)
			ofh.close()

			ofh = open(os.path.join(outdirlated, "machines.json"), "wt")
			json.dump(machines, ofh, indent=4)
			ofh.close()
		'''
	print("Total CPU Tflops:%f GPU Tflops:%f" %(total_cpu_mflops/1000, total_gpu_mflops/1000))
	print("Grand Total Tflops:%f" %((total_cpu_mflops+total_gpu_mflops)/1000))

	print("len(machines):", len(machines))
	fh = open("%s/machines.json" %(outdir), "wt")
	json.dump(machines, fh, indent=4)
	fh.close()

def curate_static_features(mach, indir, outdir, compat):
	global total_cpu_mflops
	global total_gpu_mflops

	CPU_OPS_SECOND = defaultdict(lambda: 16)
	HZ_PER_GHZ = 1000
	FLOPS_PER_MFLOPS = 10**9
	GPU_MEGAFLOPS = defaultdict(lambda: 0)
	# Flops in mega operations per second
	GPU_MEGAFLOPS.update(
		{
		"GK110BGL [Tesla K40m]": 4290,
		"GP100GL [Tesla P100 PCIe 12GB]": 9300,
		"GP100GL [Tesla P100 PCIe 16GB]": 9300,
		"GP100GL [Tesla P100 SXM2 16GB]": 9300,
		"GP102 [GeForce GTX 1080 Ti]": 11340,
		"GP102 [TITAN Xp]": 12150,
		"NVIDIA Corporation" : 14200,
		}
	)


	def find_system_vendor_product():
		vendor = None
		product = None
		for node in rectree.iter('node'):
			#print("\t\tnode attrib:", node.attrib)
			if node.attrib['class'] != 'system':
				continue
			#print('\t\tl3_node id:', l3_node.get('id'))
			product = node.find("product").text
			vendor = node.find("vendor").text
		return vendor,product

	def find_cpus_vendor_model():
		vendor = None
		processors = list()
		for node in rectree.iter('node'):
			#print("\t\tnode attrib:", node.attrib)
			if node.attrib['class'] != 'processor' or node.get('id').find("cpu:") < 0:
				continue
			#print('\t\tl3_node id:', l3_node.get('id'))
			if node.find("vendor") is None:
				print('no vendor in cpu node:', node)
				continue
			vendor = node.find("vendor").text
			processors.append(node.find("product").text)
		return vendor,processors

	def find_flops_core_thread_count():
		global total_cpu_mflops
		cores = list()
		threads = list()
		for node in rectree.iter('node'):
			#print("\t\tnode attrib:", node.attrib)
			if node.attrib['class'] != 'processor' or node.get('id').find("cpu:") < 0:
				continue
			if node.find("size") is None:
				print('no size in cpu node:', node)
				continue
			mflops = int(node.find("size").text)/FLOPS_PER_MFLOPS
			for child_node in node.iter("setting"):
				#print("\t\tnode attrib:", node.attrib)
				if child_node.get('id').find('cores') == 0:
					cores.append(int(child_node.get('value')))
				elif child_node.get('id').find('threads') == 0:
					threads.append(int(child_node.get('value')))
		return mflops, cores, threads

	def find_memory_modules():
		modules = list()
		for node in rectree.iter('node'):
			if node.get('id').find("bank:") < 0 or node.attrib['class'] != 'memory':
				continue
			#print("node id:", node.get('id'), " class:", node.attrib['class'])
			child_node = node.find('size')
			if child_node == None:
				#print("size node not found")  # DIMM slot not populated
				continue
			#print("\t\tchild_node attrib:", child_node.attrib)
			if child_node.attrib['units'] != 'bytes':
				print("unexpected units %s in size", child_node.attrib['units'])
				sys.exit(1)
			size = child_node.text
			modules.append(int(size))
		return modules

	def find_psus():
		psus = list()
		for node in rectree.iter('node'):
			if node.attrib['class'] != 'power':
				continue
			#print("node id:", node.get('id'), " class:", node.attrib['class'])
			child_node = node.find('capacity')
			if child_node == None:
				print("capacity node not found")
				continue
			#print("\t\tchild_node attrib:", child_node.attrib)
			if child_node.attrib['units'] != 'mWh':
				print("unexpected units %s in capacity", child_node.attrib['units'])
				sys.exit(1)
			cap = child_node.text
			psus.append(int(cap))
		return psus

	def find_disks():
		disks = list()
		for node in rectree.iter('node'):
			if node.get('id').find('disk') < 0:
				continue
			#print("node id:", node.get('id'), " class:", node.attrib['class'])
			child_node = node.find('size')
			if child_node == None:
				#print("size node not found")  # Faulty disk?
				continue
			#print("\t\tchild_node attrib:", child_node.attrib)
			if child_node.attrib['units'] != 'bytes':
				print("unexpected units %s in size", child_node.attrib['units'])
				sys.exit(1)
			size = child_node.text
			child_node = node.find('vendor')
			if child_node == None:
				#print("vendor node not found")  # Faulty disk?
				continue
			vend = child_node.text
			child_node = node.find('product')
			if child_node == None:
				#print("product node not found")  # Faulty disk?
				continue
			prod = child_node.text
			disks.append({"vendor": vend, "product": prod, "size": int(size)})
		return disks

	def find_nics():
		nics = list()
		for node in rectree.iter('node'):
			if node.get('id').find('network') < 0:
				continue
			#print("node id:", node.get('id'), " class:", node.attrib['class'])
			child_node = node.find('vendor')
			if child_node == None:
				#print("vendor node not found")  # Faulty disk?
				continue
			vend = child_node.text
			child_node = node.find('product')
			if child_node == None:
				#print("product node not found")  # Faulty disk?
				continue
			prod = child_node.text
			'''
			child_node = node.find('capacity')
			if child_node == None:
				print("capacity node not found for vend", vend, " prod:", prod)  # NIC not probed
				continue
			size = child_node.text
			child_node = node.find('size')
			if child_node == None:
				print("size node not found")  # NIC not probed
				continue
			print("\t\tchild_node attrib:", child_node.attrib)
			if child_node.attrib['units'] != 'bit/s':
				print("unexpected units %s in size", child_node.attrib['units'])
				sys.exit(1)
			size = child_node.text
			'''
			nics.append({"vendor": vend, "product": prod})
		return nics

	def find_accelerators():
		global total_gpu_mflops
		accelerators = list()
		for node in rectree.iter('node'):
			if node.get('id').find('display') < 0:
				continue
			#print("node id:", node.get('id'), " class:", node.attrib['class'])
			child_node = node.find('vendor')
			if child_node == None:
				#print("size node not found")  # DIMM slot not populated
				continue
			vend = child_node.text
			if vend.find("Matrox") >= 0 or vend.find("ASPEED") >= 0:
				continue
			child_node = node.find('product')
			if child_node == None:
				#print("size node not found")  # DIMM slot not populated
				continue
			prod = child_node.text
			mflops = GPU_MEGAFLOPS[prod]
			total_gpu_mflops += mflops
			accelerators.append({ "vendor" : vend, "product": prod, "mflops": mflops})
		return accelerators

	def find_user_rack_unit():
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

		return user,rack,unit

	def find_ip_address():
		if len(mach['ip_addresses']) > 0:
			ip_address = mach['ip_addresses'][0]
		return ip_address

	hostname = mach['hostname']

	curated_mach = dict()

	print("hostname:", hostname)
	#print("owner:", mach['owner'])
	#print("pool:", mach['pool']['name'])
	curated_mach['owner'] = mach['owner']
	curated_mach['pool'] = mach['pool']['name']
	curated_mach['system_id'] = mach['system_id']
	curated_mach['inband'] = True if mach['description'].find("cse_bot") >= 0 else False

	rectree = ET.parse("%s/%s-details-lshw.xml" %(outdir, hostname))
	sys_vend,sys_prod = find_system_vendor_product()
	#print("system_vendor:", sys_vend)
	#print("system_product:", sys_prod)
	curated_mach['system_vendor'] = sys_vend
	curated_mach['system_product'] = sys_prod

	mflops, cores, threads = find_flops_core_thread_count()
	curated_mach['cores'] = sum(cores)
	nthreads = sum(threads)
	ncpu_mflops = nthreads * mflops * CPU_OPS_SECOND[sys_prod]
	curated_mach['threads'] = nthreads
	curated_mach['mflops'] = ncpu_mflops
	total_cpu_mflops += ncpu_mflops

	vendor,processors = find_cpus_vendor_model()
	#print("vendor:", vendor, "processors:", processors)
	curated_mach['processor_vendor'] = vendor
	curated_mach['processor_product'] = processors

	mem_modules = find_memory_modules()
	#print("mem_size:", sum(mem_modules), "mem_modules:", mem_modules)
	curated_mach['memory_modules'] = mem_modules

	psus = find_psus()
	#print("rated_capacity:", sum(psus), "psus:", psus)
	curated_mach['psus'] = psus

	disks = find_disks()
	#print("no_of_disks:", len(disks), "disks:", disks)
	curated_mach['disks'] = disks

	nics = find_nics()
	#print("no_of_nics:", len(nics), "nics:", nics)
	curated_mach['nics'] = nics

	accelerators = find_accelerators()
	#print("no_of_accelerators:", len(accelerators), "accelerators:", accelerators)
	curated_mach['accelerators'] = accelerators
	'''
	curated_mach['power_user'] = mach['power_parameters']['power_user']
	curated_mach['power_pass'] = mach['power_parameters']['power_pass']
	curated_mach['power_driver'] = mach['power_parameters']['power_driver']
	curated_mach['power_address'] = mach['power_parameters']['power_address']
	'''
	curated_mach['ip_address'] = find_ip_address()
	curated_mach['user'], curated_mach['rack'], curated_mach['unit'] = find_user_rack_unit()

	#print("curated_mach:", hostname, curated_mach)

	return curated_mach

	'''
	fh = open("%s/%s-details-lldp.xml" %(outdir, hostname), "rt")
	lldp_buf = fh.read()
	fh.close()

	fh = open("%s/%s-details-lshw.xml" %(outdir, hostname), "rt")
	lshw_buf = fh.read()
	fh.close()

	if len(lshw_buf) == 0:
		return
	'''

	if len(lldp_buf) != 0:
		tree = ET.fromstring(lldp_buf)
		#print('interface:',tree.find('interface').text)
		interfaces = tree.findall('interface')
		for intfc in interfaces:
			chassis = intfc.find('chassis')
			vlan = intfc.find('vlan')
			print('interface:', intfc.get('name'), 'mac:', chassis.find('id').text, 'vlan:', vlan.get('vlan-id'))

def encode_inventory_data(indir, outdir, args):

	def encode_static_features(hostname, mach, indir, outdir):

		static_data = pd.DataFrame()
		#print(type(d), d)
		sys_prod_list = [ mach['system_product'] ]
		proc_prod_list = [ mach['processor_product'] ]
		disk_list = [ i['product'] for i in mach['disks'] ]
		accel_list = [ i['product'] for i in mach['accelerators'] ]
		nic_list = [ i['product'] for i in mach['nics'] ]
		# One hot encoding of features: system_vendor, system_product, processor_vendor, processor_product,
		# n-hot encoding of features: disks, accelerators, nics
		hp_list = list()
		hp_features = dict()

		# "hostname,"
		if encode_hash['hostname']['encoding'] == '1-hot':
			for k,v in sorted(encode_hash['hostname']['types'].items()) :
				hp_features["hn_"+k] = 1 if hostname == k else 0
		elif encode_hash['hostname']['encoding'] == 'label':
			hp_features["hostname"] = encode_hash['hostname']['types'][hostname]['value']

		'''
		# "system_vendor,"
		if encode_hash['system_vendor']['encoding'] == '1-hot':
			for k,v in sorted(encode_hash['system_vendor']['types'].items()) :
				hp_features["sv_"+k] = sys_prod_list.count(k)
		elif encode_hash['system_vendor']['encoding'] == 'label':
			hp_features["system_vendor"] = encode_hash['system_vendor']['types'][mach['system_vendor']]['value']
		'''

		# "system_product,"
		if encode_hash['system_product']['encoding'] == '1-hot':
			for k,v in sorted(encode_hash['system_product']['types'].items()) :
				hp_features["sp_"+k] = sys_prod_list.count(k)
		elif encode_hash['system_product']['encoding'] == 'label':
			hp_features["system_product"] = encode_hash['system_product']['types'][mach['system_product']]['value']

		'''
		# "processor_vendor,"
		if encode_hash['processor_vendor']['encoding'] == '1-hot':
			for k,v in sorted(encode_hash['processor_vendor']['types'].items()) :
				hp_features["sp_"+k] = sys_prod_list.count(k)
		elif encode_hash['processor_vendor']['encoding'] == 'label':
			hp_features["processor_vendor"] = encode_hash['processor_vendor']['types'][mach['processor_vendor']]['value']
		'''

		# "processor_product,"
		if encode_hash['processor_product']['encoding'] == '1-hot':
			for k,v in sorted(encode_hash['processor_product']['types'].items()) :
				hp_features["pp_"+k] = proc_prod_list.count(k)
		elif encode_hash['processor_product']['encoding'] == 'label':
			hp_features["processor_product"] = encode_hash['processor_product']['types'][mach['processor_product'][0]]['value']

		# "processor_count,"
		hp_features["processor_count"] = len(mach['processor_product'])

		# "processor_cores,"
		hp_features["processor_cores"] = mach['cores']

		'''
		# "processor_threads"
		hp_features["processor_threads"] = mach['threads']
		'''

		#"memory_mod_count"
		hp_features["memory_mod_count"] = len(mach['memory_modules'])

		#"memory_capacity"
		hp_features["memory_capacity"] = "%3.2f" %(sum(mach['memory_modules'])/(1000**3))

		# "accelerator_count,"
		hp_features["accelerator_count"] = len(mach['accelerators'])

		# "accelerators,"
		for k,v in sorted(encode_hash['accelerators']['types'].items()) :
			hp_features["accel_"+k] = accel_list.count(k)

		# "disk_count,"
		hp_features["disk_count"] = len(mach['disks'])

		# "disk_capacity,"
		hp_features["disk_capacity"] = "%3.2f" %(sum([ i['size'] for i in mach['disks'] ])/(1000**4))

		# "disks,"
		for k,v in sorted(encode_hash['disks']['types'].items()) :
			hp_features["disk_"+k] = disk_list.count(k)

		# "nic_count,"
		hp_features["nic_count"] = len(mach['nics'])

		# "inband,"
		hp_features["inband"] = "%d" %(mach['inband'])

		# "nics"
		for k,v in sorted(encode_hash['nics']['types'].items()) :
			hp_features["nic_"+k] = nic_list.count(k)

		# "owner,"
		hp_features["owner"] = mach['owner']

		# "pool,"
		hp_features["pool"] = mach['pool']

		# "pool,"
		hp_features["inband"] = mach['inband']

		hp_list.append(hp_features)

		static_data = pd.DataFrame(hp_list)

		static_data.to_csv(os.path.join(outdir,"%s-data-hwparts.csv"%(hostname)), index = False)
		#print(hostname, "static_data:", static_data.shape, static_data.columns)

		return static_data

	# Read & encode features, ground-truth from curated data.
	#try:
	#	with open("%s/encode_hash.json" %(args.dircumulated), "rt") as eh:
	#		encode_hash = json.load(eh)
	#except OSError:
	fh = open("%s/machines.json" %(indir), "rt")
	machines_list = json.load(fh)
	fh.close()
	print("len(machines_list):", len(machines_list))

	encode_hash = dict()
	encode_hash['hostname'] = { 'encoding': args.encoding_hostname, 'types': dict() }
	encode_hash['system_vendor'] = { 'encoding': args.encoding_system_vendor, 'types': dict() }
	encode_hash['system_product'] = { 'encoding': args.encoding_system_product, 'types': dict() }
	encode_hash['processor_vendor'] = { 'encoding': args.encoding_processor_vendor, 'types': dict() }
	encode_hash['processor_product'] = { 'encoding': args.encoding_processor_product, 'types': dict() }
	encode_hash['accelerators'] = { 'encoding': args.encoding_accelerators, 'types': dict() }
	encode_hash['disks'] = { 'encoding': args.encoding_disks, 'types': dict() }
	encode_hash['nics'] = { 'encoding': args.encoding_nics, 'types': dict() }
	encode_hash['hwconfig'] = { 'encoding': 'summary', 'types': dict() }
	# Read & encode features, ground-truth from curated data.
	# find unique system_product names
	for hostname in machines_list:
		fh = open("%s/%s-machine.json" %(indir, hostname), "rt")
		mach = json.load(fh)
		fh.close()
		#print("mach:", mach)
		#if not hostname == "sudarshan":
		#	continue

		#print("===============================")
		# "hostname"
		if hostname not in encode_hash['hostname']['types']:
			stat = { 'shape': [0, 0] }
			dyn = { 'shape': [0, 0],
				'classes' : {	0 : 0, 1 : 0, 2 : 0, 3 : 0 } }
			encode_hash['hostname']['types'][hostname] = {
					'value' : len(encode_hash['hostname']['types']),
					'static' : stat, 'dynamic' : dyn }

		# "system_vendor"
		vend = mach['system_vendor']
		if vend not in encode_hash['system_vendor']['types']:
			encode_hash['system_vendor']['types'][vend] = {
					'value' : len(encode_hash['system_vendor']['types']),
					'machines' : list() }
		if hostname not in encode_hash['system_vendor']['types'][vend]['machines']:
			encode_hash['system_vendor']['types'][vend]['machines'].append(hostname)

		# "system_product"
		prod = mach['system_product']
		if prod not in encode_hash['system_product']['types']:
			encode_hash['system_product']['types'][prod] = {
					'value' : len(encode_hash['system_product']['types']),
					'machines' : list() }
		if hostname not in encode_hash['system_product']['types'][prod]['machines']:
			encode_hash['system_product']['types'][prod]['machines'].append(hostname)

		# "processor_vendor"
		vend = mach['processor_vendor']
		if vend not in encode_hash['processor_vendor']['types']:
			encode_hash['processor_vendor']['types'][vend] = {
					'value' : len(encode_hash['processor_vendor']['types']),
					'machines' : list() }
		if hostname not in encode_hash['processor_vendor']['types'][vend]['machines']:
			encode_hash['processor_vendor']['types'][vend]['machines'].append(hostname)

		# "processor_product"
		prod = mach['processor_product']
		for p in prod:
			if p not in encode_hash['processor_product']['types']:
				encode_hash['processor_product']['types'][p] = {
						'value' : len(encode_hash['processor_product']['types']),
						'machines' : list() }
			if hostname not in encode_hash['processor_product']['types'][p]['machines']:
				encode_hash['processor_product']['types'][p]['machines'].append(hostname)

		# "accelerators"
		accel = mach['accelerators']
		for a in accel:
			if a['product'] not in encode_hash['accelerators']['types']:
				encode_hash['accelerators']['types'][a['product']] = {
						'value' : len(encode_hash['accelerators']['types']),
						'machines' : list() }
			if hostname not in encode_hash['accelerators']['types'][a['product']]['machines']:
				encode_hash['accelerators']['types'][a['product']]['machines'].append(hostname)

		# "disks"
		disks = mach['disks']
		for d in disks:
			if d['product'] not in encode_hash['disks']['types']:
				encode_hash['disks']['types'][d['product']] = {
						'value' : len(encode_hash['disks']['types']),
						'machines' : list() }
			if hostname not in encode_hash['disks']['types'][d['product']]['machines']:
				encode_hash['disks']['types'][d['product']]['machines'].append(hostname)

		# "nics"
		nic = mach['nics']
		for n in nic:
			if n['product'] not in encode_hash['nics']['types']:
				encode_hash['nics']['types'][n['product']] = {
						'value' : len(encode_hash['nics']['types']),
						'machines' : list() }
			if hostname not in encode_hash['nics']['types'][n['product']]['machines']:
				encode_hash['nics']['types'][n['product']]['machines'].append(hostname)

	'''
	print("encode_hash['hostname']:", len(encode_hash['hostname']))
	print("encode_hash['system_vendor']:", len(encode_hash['system_vendor']))
	print("encode_hash['system_product']:", len(encode_hash['system_product']))
	print("encode_hash['processor_vendor']:", len(encode_hash['processor_vendor']))
	print("encode_hash['processor_vendor']:", encode_hash['processor_vendor'])
	print("encode_hash['processor_product']:", len(encode_hash['processor_product']))
	print("encode_hash['processor_product']:", encode_hash['processor_product'])
	print("encode_hash['accelerators']:", encode_hash['accelerators'])
	print("encode_hash['disks']:", encode_hash['disks'])
	print("encode_hash['nics']:", encode_hash['nics'])
	'''
	# Read & encode features, ground-truth from curated data.
	encoded_data_hash = dict()
	hw_config = pd.DataFrame()
	distinct_hw_config = pd.DataFrame()
	for hostname in machines_list:
		#print(hostname)
		fh = open("%s/%s-machine.json" %(indir, hostname), "rt")
		mach = json.load(fh)
		fh.close()
		#print("mach:", mach)
		#if not (hostname == "l1055-dgx1" or hostname == "candle01"):
		#	continue
		encoded_data_hash[hostname] = { "static" : pd.DataFrame(), "dynamic" : pd.DataFrame() }

		static_data = encode_static_features(hostname, mach, indir, outdir)
		if static_data.shape[0] == 0:
			continue

		stat = { 'shape': [static_data.shape[0], static_data.shape[1]] }
		encode_hash['hostname']['types'][hostname]['static'] = stat

		key = "%s" %(static_data.drop(columns=['hostname', 'owner', 'pool', 'inband'], axis=1).to_csv(header=False, index=False).strip())
		#print("key:", key)
		if key not in encode_hash['hwconfig']['types']:
			encode_hash['hwconfig']['types'][key] = {
					'value' : len(encode_hash['hwconfig']['types']),
					'machines' : list() }
		if hostname not in encode_hash['hwconfig']['types'][key]['machines']:
			encode_hash['hwconfig']['types'][key]['machines'].append(hostname)
		encoded_data_hash[hostname]["static"] = static_data

	'''
	print("Distinct hw_configs:", distinct_hw_config.shape[0])
	print("Total hw_configs:", hw_config.shape[0],
		"Distinct hw_configs:", hw_config.drop('hostname', axis=1).drop_duplicates(subset=None, keep='first', inplace=False).shape[0])
	'''
	fh = open("%s/encode_hash.json" %(outdir), "wt")
	json.dump(encode_hash, fh, indent=4, sort_keys=True)
	fh.close()

	ofh_mcs = open("%s/machines.json" %(outdir), "wt")
	json.dump(machines_list, ofh_mcs, indent=4, sort_keys=True)
	ofh_mcs.close()

def find_feasible_subset(indir, outdir):
	fh = open("%s/machines.json" %(indir), "rt")
	machines_list = json.load(fh)
	fh.close()
	print("len(machines_list):", len(machines_list))

	fh = open("%s/encode_hash.json" %(indir), "rt")
	encode_hash = json.load(fh)
	fh.close()
	print("len(hwconfig):", len(encode_hash['hwconfig']['types']))

	# Find a feasible subset
	# TODO
	# For now feasible machines are only three
	#machines_list_subset = [ "penna", "sindhu", "candle03", "candle04" ]
	machines_list_subset = [ "softran4", "candle03", "candle04" ]

	# Save results to files
	fh = open("%s/machines_subset.json" %(outdir), "wt")
	json.dump(machines_list_subset, fh, indent=4, sort_keys=True)
	fh.close()
	print("len(machines_list_subset):", len(machines_list_subset))

def run_benchmark_on_host(ts, hostname, outdir_raw_bm, bm, mach, queue, skip_host):
	global shutdown
	shutdown = multiprocessing.Event()
	# Plant a signal handler for Ctrl+C
	signal.signal(signal.SIGINT, sigint_handler)

	# Temporary return
	if skip_host:
		time.sleep(20)
		queue.put(True)
		# Sleep few extra secs to make fetch_bmc_data process get out gracefully, lest the BMC f/w goes into bad state.
		time.sleep(10)
		return

	test_id = -1
	# Start the benchmark.
	out_hand = open(os.path.join(outdir_raw_bm,"%s-%s-%s-machine-test-out.txt" %(ts, hostname, bm)), "wt")
	err_hand = open(os.path.join(outdir_raw_bm,"%s-%s-%s-machine-test-err.txt" %(ts, hostname, bm)), "wt")
	p = subprocess.run(["maas", "cse_bot", "machine", "test", mach['system_id'], "testing_scripts=%s" %(bm) ],
			cwd=outdir_raw_bm, stdout=out_hand, stderr=err_hand, timeout=60)
	out_hand.close()
	err_hand.close()
	if p.returncode != 0:
		queue.put(True)
		# Sleep few extra secs to make fetch_bmc_data process get out gracefully, lest the BMC f/w goes into bad state.
		time.sleep(10)
		return

	# Wait for the benchmark to complete (succeed or fail)

	while not shutdown.is_set() and queue.empty():
		out_hand = open(os.path.join(outdir_raw_bm,"%s-%s-%s-node-script-result-read-out.txt" %(ts, hostname, bm)), "wt")
		err_hand = open(os.path.join(outdir_raw_bm,"%s-%s-%s-node-script-result-read-err.txt" %(ts, hostname, bm)), "wt")
		p = subprocess.run(["maas", "cse_bot", "node-script-result", "read", mach['system_id'], "current-testing" ],
				cwd=outdir_raw_bm, stdout=out_hand, stderr=err_hand, timeout=60)
		out_hand.close()
		err_hand.close()
		if p.returncode != 0:
			break
		out_hand = open(os.path.join(outdir_raw_bm,"%s-%s-%s-node-script-result-read-out.txt" %(ts, hostname, bm)), "rt")
		res = json.load(out_hand)
		out_hand.close()
		print(hostname, "status: ", res['status_name'])
		if res['status_name'] not in ["Pending", "Running"]:
			test_id = res['id']
			break
		time.sleep(60)

	queue.put(True)
	# Sleep few extra secs to make fetch_bmc_data process get out gracefully, lest the BMC f/w goes into bad state.
	time.sleep(10)

	return

def maas_login(user, outdir):
	#os.system("maas login cse_bot http://regctrl.comp.iith.ac.in:5240/MAAS/api/2.0 - < /etc/dhi-ojas/cse_bot-apikey")
	out_hand = open(os.path.join(outdir,"maas-login-out.txt"), "wt")
	err_hand = open(os.path.join(outdir,"maas-login-err.txt"), "wt")
	in_hand = open("/etc/dhi-ojas/cse_bot-apikey", "rt")
	p = subprocess.run(["maas", "login", user, "http://regctrl.comp.iith.ac.in:5240/MAAS/api/2.0", "-" ],
			cwd=outdir, stdin=in_hand, stdout=out_hand, stderr=err_hand, timeout=60)
	in_hand.close()
	out_hand.close()
	err_hand.close()
	if p.returncode != 0:
		print("maas login %s failed" %(user))
		return
	return

def maas_logout(user, outdir):
	out_hand = open(os.path.join(outdir,"maas-logout-out.txt"), "wt")
	err_hand = open(os.path.join(outdir,"maas-logout-err.txt"), "wt")
	p = subprocess.run(["maas", "logout", user],
			cwd=outdir, stdout=out_hand, stderr=err_hand, timeout=60)
	out_hand.close()
	err_hand.close()
	if p.returncode != 0:
		print("maas logout %s failed" %(user))
		return
	return

def get_benchmark_result(ts, hostname, system_id, bm, outdir_raw_bm):
	result = None
	wtype = 'benchmark'

	out_hand = open(os.path.join(outdir_raw_bm,"%s-%s-%s-node-script-result-read-out.txt" %(ts, hostname, bm)), "wt")
	err_hand = open(os.path.join(outdir_raw_bm,"%s-%s-%s-node-script-result-read-err.txt" %(ts, hostname, bm)), "wt")
	p = subprocess.run(["maas", "cse_bot", "node-script-result", "read", system_id, "current-testing" ],
			cwd=outdir_raw_bm, stdout=out_hand, stderr=err_hand, timeout=60)
	out_hand.close()
	err_hand.close()
	if p.returncode != 0:
		print("maas node-script-result %s failed" %(hostname))
		return result

	out_hand = open(os.path.join(outdir_raw_bm,"%s-%s-%s-node-script-result-read-out.txt" %(ts, hostname, bm)), "rt")
	res = json.load(out_hand)
	out_hand.close()

	print("Status: ", res['status_name'])
	if res['status_name'] not in ["Passed"]:
		print("test has not passed on %s" %(hostname))
		return
	test_id = res['id']

	#os.system("maas cse_bot node-script-result download 6h4d8g current-testing output=all filetype=tar.xz > result.tar.xz")
	xzfile = "%s-%s.tar.xz" %(hostname, bm)
	yamlfile = "%s-testing-%d/%s.yaml" %(hostname, test_id, bm)
	out_hand = open(os.path.join(outdir_raw_bm, xzfile), "wb")
	err_hand = open(os.path.join(outdir_raw_bm,"%s-%s-%s-node-script-result-download.txt" %(ts, hostname, bm)), "wt")
	p = subprocess.run(["maas", "cse_bot", "node-script-result", "download", system_id,
			"current-testing", "output=all", "filetype=tar.xz" ],
			cwd=outdir_raw_bm, stdout=out_hand, stderr=err_hand, timeout=60)
	out_hand.close()
	err_hand.close()
	p = subprocess.run(["tar", "-xJf", xzfile], cwd=outdir_raw_bm, timeout=60)

	data = yaml.load(open(os.path.join(outdir_raw_bm, yamlfile)))
	fh = open(os.path.join(outdir_raw_bm, "%s_%03d-%s-%s-%s-host_data.json" %(ts, 000, hostname, bm, wtype)), "wt")
	json.dump(data, fh, indent=4)
	fh.close()

def run_benchmarks_on_machine(hostname, indir_enc_inv, outdir_raw_bm, benchmarks, skip_host):
	wtype = 'benchmark'

	indir_raw_inv = os.path.join(indir_enc_inv, "..", "a_raw_inventory")
	indir_cur_inv = os.path.join(indir_enc_inv, "..", "b_curated_inventory")

	machines = dict()

	fh = open("%s/%s-machine.json" %(indir_cur_inv, hostname), "rt")
	mach = json.load(fh)
	fh.close()
	#print("mach:", mach)
	#if not (hostname == "l1055-dgx1" or hostname == "candle01"):
	#	continue
	mach['hostname'] = hostname

	if 'power_parameters' not in mach:
		fh = open("%s/%s-power_parameters.json" %(indir_raw_inv, hostname), "rt")
		power_parameters = json.load(fh)
		fh.close()
		#print("power_parameters:", power_parameters)
		for k,v in power_parameters.items():
			#print('k:', k, 'v:', v)
			mach[k] = v

	mach_obj = my_machine_lib.factory.get_type(mach['system_product'], mach)

	print("starting benchmarks on", hostname)
	for bm in benchmarks:
		print("running %s benchmark" %(bm))

		ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

		# create a queue for synchroniation
		queue = multiprocessing.Queue()

		# create two child processes
		bmcjob  = multiprocessing.Process(target = mach_obj.fetch_bmc_data, args = (ts, outdir_raw_bm, wtype, bm, queue), daemon=True)
		hostjob = multiprocessing.Process(target = run_benchmark_on_host, args = (ts, hostname, outdir_raw_bm, bm, mach, queue, skip_host), daemon=True)

		# start the child processes
		hostjob.start()
		bmcjob.start()

		# wait for the children to join back
		hostjob.join()
		bmcjob.join()

		if not skip_host:
			get_benchmark_result(ts, hostname, mach['system_id'], bm, outdir_raw_bm)

	print("finished benchmarks on", hostname)

def run_benchmarks(indir_enc_inv, indir_inv_sub, outdir_raw_bm, benchmarks, skip_host, skip_bmc):
	print(benchmarks)

	maas_login('cse_bot', outdir_raw_bm)

	fh = open("%s/machines_subset.json" %(indir_inv_sub), "rt")
	machines_subset = json.load(fh)
	fh.close()
	print("len(machines_subset):", len(machines_subset))

	fh = open("%s/encode_hash.json" %(indir_enc_inv), "rt")
	encode_hash = json.load(fh)
	fh.close()
	print("len(hwconfig):", len(encode_hash['hwconfig']['types']))

	# start the child processes
	joblist = list()
	for hostname in machines_subset:
		job = multiprocessing.Process(target = run_benchmarks_on_machine, args = (hostname, indir_enc_inv, outdir_raw_bm, benchmarks, skip_host))
		job.start()
		joblist.append(job)

	# wait for the children to join back
	for job in joblist:
		job.join()

	maas_logout('cse_bot', outdir_raw_bm)

sys.path.append('../lib/')
sys.path.append('/usr/local/lib/python3.6/dist-packages/dhi-ojas/')
import my_machine_lib

def collect_realdata(indir_enc_inv, indir_inv_sub, outdir_raw_wl, wl, skip_host, skip_bmc, bmc_type):
	global shutdown
	shutdown = multiprocessing.Event()

	fh = open("%s/machines_subset.json" %(indir_inv_sub), "rt")
	machines_subset = json.load(fh)
	fh.close()
	print("len(machines_subset):", len(machines_subset))

	fh = open("%s/encode_hash.json" %(indir_enc_inv), "rt")
	encode_hash = json.load(fh)
	fh.close()
	print("len(hwconfig):", len(encode_hash['hwconfig']['types']))

	# start the child processes
	joblist = list()
	for hostname in machines_subset:
		job = multiprocessing.Process(target = collect_realdata_from_machine, args = (hostname, indir_enc_inv, outdir_raw_wl, wl, skip_host, bmc_type))
		job.start()
		joblist.append(job)

	while not shutdown.is_set():
		time.sleep(1)

	# wait for the children to join back
	for job in joblist:
		job.join()

def collect_realdata_from_machine(hostname, indir_enc_inv, outdir_raw_wl, wl, skip_host, bmc_type):

	global shutdown
	shutdown = multiprocessing.Event()
	# Plant a signal handler for Ctrl+C
	signal.signal(signal.SIGINT, sigint_handler)

	indir_raw_inv = os.path.join(indir_enc_inv, "..", "a_raw_inventory")
	indir_cur_inv = os.path.join(indir_enc_inv, "..", "b_curated_inventory")

	fh = open("%s/%s-machine.json" %(indir_cur_inv, hostname), "rt")
	mach = json.load(fh)
	fh.close()
	#print("mach:", mach)
	#if not (hostname == "l1055-dgx1" or hostname == "candle01"):
	#	continue
	mach['hostname'] = hostname

	if 'power_parameters' not in mach:
		fh = open("%s/%s-power_parameters.json" %(indir_raw_inv, hostname), "rt")
		power_parameters = json.load(fh)
		fh.close()
		#print("power_parameters:", power_parameters)
		for k,v in power_parameters.items():
			#print('k:', k, 'v:', v)
			mach[k] = v

	mach_obj = my_machine_lib.factory.get_type(mach['system_product'], mach)

	ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

	# create a queue for synchroniation
	global queue
	queue = multiprocessing.Queue()

	wtype = "production"
	# create two child processes
	bmcjob  = multiprocessing.Process(target = mach_obj.fetch_bmc_data, args = (ts, outdir_raw_wl, wtype, wl, queue, bmc_type), daemon=True)
	hostjob = multiprocessing.Process(target = mach_obj.fetch_host_data, args = (ts, outdir_raw_wl, skip_host, wtype, wl, queue), daemon=True)

	# start the child processes
	hostjob.start()
	bmcjob.start()

	while not shutdown.is_set() and queue.empty():
		time.sleep(1)

	# wait for the children to join back
	hostjob.join()
	bmcjob.join()

def curate_measurement_data(indir_cur_inv, indir_enc_inv, indir_inv_sub, indir_raw_mmd, outdir_cur_mmd, wtype, drift_interval, workloads):

	fh = open("%s/machines.json" %(indir_enc_inv), "rt")
	machines_list = json.load(fh)
	fh.close()
	print("len(machines_list):", len(machines_list))

	fh = open("%s/machines_subset.json" %(indir_inv_sub), "rt")
	machines_list_sub = json.load(fh)
	fh.close()
	print("len(machines_list_sub):", len(machines_list_sub))

	# Read features from downloaded benchmark data.
	for hostname in machines_list_sub:
		mach_file = os.path.join(indir_cur_inv, "%s-machine.json" %(hostname))
		if not os.path.isfile(mach_file):
			print(mach_file, "not found")
			continue
		ifh = open(mach_file, "rt")
		mach = json.load(ifh)
		ifh.close()
		#print("mach:", mach)
		#if not (hostname == "l1055-dgx1" or hostname == "candle01"):
		#	continue

		#print("===============================")
		#print("hostname:", hostname)
		curate_measurement_data_from_machine(hostname, mach, indir_raw_mmd, outdir_cur_mmd, wtype, drift_interval, workloads)

def curate_measurement_data_from_machine(hostname, mach, indir, outdir, wtype, drift_interval, workloads):

	curated_data_file = "%s-%s-data.json" %(hostname, wtype)
	curated_data=dict()
	#restr = r"([0-9]+)_([0-9]+)-%s-*_data.json" %(hostname)
	restr = r"*%s*.json" %(hostname)
	#print(restr)
	match_files = dict()

	for wl in workloads:
		# 20200522_022630_000-candle02-nascent_idle_benchmark-bmc_data.json
		file_list = glob.glob(os.path.join(indir,'*_*_*-%s-%s-*_data.json' %(hostname, wl)))
		#print("indir:", indir, "file_list", file_list)
		for pname1 in file_list:
			fname1 = os.path.basename(pname1)
			if 'bmc_data' not in fname1 or wl not in fname1:
				continue
			ts1 = fname1.split('-')[0]
			for pname2 in file_list:
				fname2 = os.path.basename(pname2)
				ts2 = fname2.split('-')[0]
				if ts1 != ts2:
					#print("skipping fname1:", fname1, "fname2:", fname2)
					continue
				if 'host_data' not in fname2:
					#print("skipping fname1:", fname1, "fname2:", fname2)
					continue
				#print("selecting fname1:", fname1, "fname2:", fname2)
				match_files[ts1] = { 'host_data' : pname2, 'bmc_data' : pname1}

	print(match_files)

	for k,v in match_files.items():
		bmc_data_file = v['bmc_data']
		host_data_file = v['host_data']
		print("processing %s's %s %s" %(hostname, bmc_data_file, host_data_file))
		bmc = open(bmc_data_file)
		host = open(host_data_file)
		bmc_dict = json.load(bmc)
		host_dict = json.load(host)
		bmc.close()
		host.close()

		host_dict_items = sorted(host_dict.items())
		bmc_dict_items = sorted(bmc_dict.items())
		for bk,bv in bmc_dict_items:
			btime = datetime.strptime(bk, '%Y-%m-%d %H:%M:%S.%f').timestamp() - drift_interval
			for hk,hv in host_dict_items:
				htime = datetime.strptime(hk, '%Y-%m-%d %H:%M:%S.%f').timestamp()
				#htime = datetime.strptime(hk, '%Y-%m-%d %H:%M:%S').timestamp()
				if abs(float(btime - htime)) >= 1:
					continue
				if 'loadavg' in hv and hv['loadavg'] < 0:
					continue
				if 'util' in hv and hv['util'] < 0:
					continue
				if 'power_p0' in hv and 'power_p0' in hv:
					if hv['power_p0'] < 0 or hv['power_p1'] < 0:
						continue
					bv['power_px'] = hv['power_p0'] + hv['power_p1']
				if 'power' in bv and bv['power'] < 0:
					continue
				if 'inlet_temp' in bv and bv['inlet_temp'] < 0:
					continue
				curated_data[bk] = bv
				for k in hv:
					curated_data[bk][k] = hv[k]
				break

	with open(os.path.join(outdir, curated_data_file), 'wt') as fp:
		#print("creating ", os.path.join(outdir, curated_data_file))
		json.dump(curated_data, fp, indent=4, sort_keys=True)

	return

def encode_data(indir_cur_inv, indir_enc_inv, indir_inv_sub, indir_cur_data, wtype,
		outdir_enc_data, encoding_inlet_temp=None,
		encoding_exhaust_temp=None, encoding_fans_speed=None, cpuload_threshold=0.0,
		encoding_cpu_power=None, encoding_fan_power=None, encoding_systemboard_power=None, encoding_hdd_power=None,
		encoding_overall_power='as-is', encoding_cpuload='as-is',
		include_timestamp=True, gt='cpuload', debug=False):

	def encode_loadavg(loadavg_raw):
		if loadavg_raw < 0.03:
			load_class = 0
		elif loadavg_raw >= 0.03 and loadavg_raw <= 10:
			load_class = 1
		elif loadavg_raw > 10 and loadavg_raw <= 40:
			load_class = 2
		elif loadavg_raw > 40:
			load_class = 3
		return load_class

	def encode_cpuload(cpuload_raw):
		if encoding_cpuload == 'class':
			if cpuload_raw <= cpuload_threshold:
				load_class = 0
			elif cpuload_raw > cpuload_threshold and cpuload_raw <= 10:
				load_class = 1
			elif cpuload_raw > 10 and cpuload_raw <= 40:
				load_class = 2
			elif cpuload_raw > 40:
				load_class = 3
			return load_class
		elif encoding_cpuload == 'as-is':
			return cpuload_raw

	def encode_dynamic_features(hostname, indir, wtype, outdir):

		ifh = open("%s/%s-%s-data.json" %(indir, hostname, wtype), "rt")
		data = json.load(ifh)
		ifh.close()

		print(hostname, "len(data):", len(data))
		sr_list = list()
		gt_list = list()
		for k,v in data.items():
			if gt == 'loadavg':
				if v['loadavg'] < 0:
					continue
			else:
				if v['cpuload_total'] < 0:
					continue
			if 'power' in v and v['power'] < 0:
				continue
			if 'util' in v and v['util'] < 0:
				continue
			if 'inlet_temp' not in v:
				pass
				#print(k, v)
			if encoding_inlet_temp == "as-is" and v['inlet_temp'] < 0:
				continue
			#print(k, ":", v)
			sr_features = { "time": k }
			if(encoding_overall_power =="as-is"):
				sr_features['overall_power'] =  v['power']
			elif(encoding_overall_power =="host"):
				sr_features['overall_power'] =  v['power_px']
			if(encoding_cpu_power == "as-is"):
				if 'CPU1 Power' in v or 'CPU2 Power' in v:
					if v['CPU1 Power'] < 0 or v['CPU2 Power'] < 0:
						continue
					sr_features['cpu_power'] = v['CPU1 Power'] + v['CPU2 Power']
				if 'cpu_power' in v:
					if v['cpu_power'] < 0:
						continue
					sr_features['cpu_power'] = v['cpu_power']
			if encoding_fan_power == "as-is":
				if v['fan_power'] < 0:
					continue
				sr_features['fan_power'] = v['fan_power']
			if encoding_hdd_power == "as-is":
				if v['hdd_power'] < 0:
					continue
				sr_features['hdd_power'] = v['hdd_power']
			if encoding_systemboard_power == "as-is":
				if v['systemboard_power'] < 0:
					continue
				sr_features['systemboard_power'] = v['systemboard_power']
			if encoding_inlet_temp == "as-is":
				if v['inlet_temp'] < 0:
					continue
				sr_features["inlet_temp"] = v['inlet_temp']
			if encoding_exhaust_temp == "as-is":
				if v['exhaust_temp'] < 0:
					continue
				sr_features["exhaust_temp"] = v['exhaust_temp']
			if encoding_fans_speed == "as-is":
				skip = False
				for fk, fv in v.items():
					if not re.search('Fan', fk, re.IGNORECASE):
						continue
					if v[fk] < 0 or fv is None:
						skip = True
						break
					sr_features[fk] = fv
				if skip:
					continue
			sr_list.append(sr_features)

			gt_features = {
				"time": k,
				"util": 0 if v['cpuload_total'] <= cpuload_threshold else 1,
				"load": encode_cpuload(v['cpuload_total']) if gt == "cpuload" else encode_loadavg(v['loadavg'])
			}
			gt_list.append(gt_features)

		sensor_data = pd.DataFrame(sr_list)
		#print(hostname, "sensor_data:", sensor_data.shape, sensor_data.columns)

		groundtruth_data = pd.DataFrame(gt_list)
		#print(hostname, "groundtruth:", groundtruth_data.shape, groundtruth_data.columns)

		if groundtruth_data.shape[0] == 0 or sensor_data.shape[0] == 0:
			return pd.DataFrame()

		if not include_timestamp:
			dynamic_data = pd.merge(sensor_data, groundtruth_data, on='time').drop('time', axis=1)
		else:
			dynamic_data = pd.merge(sensor_data, groundtruth_data, on='time')
		#print(hostname, "dynamic_data:", dynamic_data.shape, dynamic_data.columns)
		if debug:
			dynamic_data.to_csv(os.path.join(outdir,'%s-dynamic_data.csv'%(hostname)), index = False)

		if debug:
			sensor_data.drop('time', axis=1).to_csv(os.path.join(outdir,"%s-data-sensors.csv"%(hostname)), index = False)
			groundtruth_data.drop('time', axis=1).to_csv(os.path.join(outdir,"%s-data-groundtruth.csv"%(hostname)), index = False)

		return dynamic_data

	# Read & encode features, ground-truth from curated data.
	with open(os.path.join(indir_enc_inv, "encode_hash.json"), "rt") as eh:
		encode_hash = json.load(eh)

	fh = open("%s/machines.json" %(indir_enc_inv), "rt")
	machines_list = json.load(fh)
	fh.close()
	print("len(machines_list):", len(machines_list))

	fh = open("%s/machines_subset.json" %(indir_inv_sub), "rt")
	machines_list_sub = json.load(fh)
	fh.close()
	print("len(machines_list_sub):", len(machines_list_sub))
	print("Encoding cpuload threshold as: ", cpuload_threshold)

	# Read & encode features, ground-truth from curated data.
	encoded_data_hash = dict()
	hw_config = pd.DataFrame()
	distinct_hw_config = pd.DataFrame()
	for hostname in machines_list_sub:
		#print(hostname)
		fh = open(os.path.join(indir_cur_inv, "%s-machine.json" %(hostname)), "rt")
		mach = json.load(fh)
		fh.close()
		#print("mach:", mach)
		#if not (hostname == "l1055-dgx1" or hostname == "candle01"):
		#	continue
		encoded_data_hash[hostname] = { "static" : pd.DataFrame(), "dynamic" : pd.DataFrame() }

		dynamic_data = encode_dynamic_features(hostname, indir_cur_data, wtype, outdir_enc_data)
		if dynamic_data.shape[0] == 0:
			continue

		if encoding_cpuload == 'class':
			dyn = { 'shape': [dynamic_data.shape[0], dynamic_data.shape[1]],
				'uclass' : {	0 : len(dynamic_data[(dynamic_data.util==0)]) ,
						1 : len(dynamic_data[(dynamic_data.util==1)]) },
				'lclass' : {	0 : len(dynamic_data[(dynamic_data.load==0)]) ,
						1 : len(dynamic_data[(dynamic_data.load==1)]) ,
						2 : len(dynamic_data[(dynamic_data.load==2)]) ,
						3 : len(dynamic_data[(dynamic_data.load==3)]) } }
		elif encoding_cpuload == 'as-is':
			dyn = { 'shape': [dynamic_data.shape[0], dynamic_data.shape[1]],
				'uclass' : {	0 : len(dynamic_data[(dynamic_data.util<=cpuload_threshold)]) ,
						1 : len(dynamic_data[(dynamic_data.util>cpuload_threshold)]) },
				'lclass' : {	0 : len(dynamic_data[(dynamic_data.load<=cpuload_threshold)]),
						1 : len(dynamic_data[(dynamic_data.load>cpuload_threshold) & (dynamic_data.load<=10)]),
						2 : len(dynamic_data[(dynamic_data.load>10) & (dynamic_data.load<=40)]) ,
						3 : len(dynamic_data[(dynamic_data.load>cpuload_threshold)]) } }
		encode_hash['hostname']['types'][hostname]['dynamic'] = dyn

		encoded_data_hash[hostname]["dynamic"] = dynamic_data

	#encoded_data = pd.DataFrame()
	for hostname in machines_list_sub:
		xfile = '%s-X.csv' %(hostname)
		yfile = '%s-y.csv' %(hostname)
		encode_hash['hostname']['types'][hostname]['X'] = xfile
		encode_hash['hostname']['types'][hostname]['y'] = ""

		static_data = encoded_data_hash[hostname]["static"]
		dynamic_data = encoded_data_hash[hostname]["dynamic"]

		'''
		print("hostname:", hostname, " static:", static_data.shape,
			"dynamic:", dynamic_data.shape, "\n",
			"columns:", static_data.columns)
		'''

		host_data = dynamic_data
		#print(hostname, "newdata:", newdata.shape, newdata.columns)
		#print(hostname, "new_data:", new_data.shape)
		#if args.debug:
		#	new_data.to_csv(os.path.join(outdir,'%s-new_data.csv'%(hostname)), index=False)

		if dynamic_data.shape[0] == 0:
			continue

		# TODO prune nan values in the above function lest debug files are use-less
		host_data = host_data[host_data.util >= 0].dropna()
		#host_data = host_data[host_data.util >= 0]
		X = host_data[host_data.load >= 0]
		if not include_timestamp:
			y = X[['util', 'load']]
		else:
			y = X[['time', 'util', 'load']]
		X = X.drop(['util','load'],axis = 1)

		y = pd.DataFrame(y)

		dyn = encode_hash['hostname']['types'][hostname]['dynamic']
		print("Hostname: ", hostname)
		print("Number of Samples in Zero Class:", dyn['lclass'][0])
		print("Number of Samples in Non-zero Class:", dyn['lclass'][1] + dyn['lclass'][2] + dyn['lclass'][3])
		print("Non-zero class data distribution")
		print("Number of Samples in Class 1:", dyn['lclass'][1])
		print("Number of Samples in Class 2:", dyn['lclass'][2])
		print("Number of Samples in Class 3:", dyn['lclass'][3])

		X.to_csv(os.path.join(outdir_enc_data, xfile), index=False)
		y.to_csv(os.path.join(outdir_enc_data, yfile), index=False)
		encode_hash['hostname']['types'][hostname]['y'] = yfile

		#encoded_data = encoded_data.append(host_data, ignore_index = True)

	#print("encoded_data.shape:", encoded_data.shape)

	#if args.debug:
	#	encoded_data.to_csv(os.path.join(outdir,'encoded_data.csv'), index=False)

	fh = open(os.path.join(outdir_enc_data, "encode_hash.json"), "wt")
	print(type(encode_hash))
	json.dump(encode_hash, fh, indent=4, sort_keys=True)
	fh.close()

	ofh_mcs = open(os.path.join(outdir_enc_data, "machines.json"), "wt")
	json.dump(machines_list, ofh_mcs, indent=4, sort_keys=True)
	ofh_mcs.close()

def generate_model(indir_enc_inv, indir_inv_sub, indir_enc_bm, train_machines, indir_enc_prd,
		test_machines, selection, correlation, nexperiments, ctype, method, outdir_model,
		plot_graphs,start,end , lower_bound_cpuload, upper_bound_cpuload):

	# Read & encode features, ground-truth from curated data.
	with open(os.path.join(indir_enc_inv, "encode_hash.json"), "rt") as eh:
		encode_hash = json.load(eh)

	fh = open("%s/machines.json" %(indir_enc_inv), "rt")
	machines_list = json.load(fh)
	fh.close()
	print("len(machines_list):", len(machines_list))

	fh = open("%s/machines_subset.json" %(indir_inv_sub), "rt")
	machines_list_sub = json.load(fh)
	fh.close()
	print("len(machines_list_sub):", len(machines_list_sub))

	if ctype == 'binary':
		adj = 0
	elif ctype == 'multi':
		adj = 0

	fh = open(os.path.join(indir_enc_bm, "encode_hash.json"), "rt")
	encode_hash = json.load(fh)
	fh.close()

	hwconfig_hash = encode_hash['hwconfig']['types']
	hostname_hash = encode_hash['hostname']['types']
	print("len(hwconfig_hash):", len(hwconfig_hash))
	print("len(hostname_hash):", len(hostname_hash))

	if  len(train_machines) > 0 or len(test_machines) > 0:
		# check if all machines are from same
		print("train machines:", train_machines)
		print("test machines:", test_machines)
		print("==========================================================")
		results_train = list()
		results_test = list()
		for i in range(int(nexperiments)):
			print("----------------------------------------------------------")
			(model, result_train) = train_model(train_machines, indir_enc_bm,
								outdir_model, selection, correlation,
								ctype, method, plot_graphs, start, end)
			print('train_test type(model)', type(model))
			results_train.append(result_train)
			if len(test_machines) == 0:
				continue
			(result_test) = test_model(test_machines, indir_enc_prd,
							outdir_model, model,  correlation,
							ctype, method, plot_graphs,start,end,
							lower_bound_cpuload, upper_bound_cpuload)
			results_test.append(result_test)
			print("----------------------------------------------------------")
		print_results("train", ctype, results_train)
		if len(test_machines) > 0:
			print_results("test", ctype, results_test)
		print("==========================================================")
	else:
		# For each distinct h/w config 'v',
		#   For each machine having the h/w config 'v'
		#	if there are non-zero no of data-samples
		#		read X.csv, and Y.csv for the machine
		#		merge in train_d
		#		remember the machine's enocoded-id in a list 'value'
		#		create dataframe X concat y

		new_hwconfig_hash = dict()
		for k,v in hwconfig_hash.items():
			machine_with_nzdata = 0
			machines = list()
			for m in v['machines']:
				print("hostname:", m)
				if hostname_hash[m]['dynamic']['shape'][0] == 0:
					continue
				print(m,hostname_hash[m]['dynamic']['shape'][0])
				machines.append(m)
				machine_with_nzdata += 1
			if machine_with_nzdata > 0:
				new_hwconfig_hash[k] = { 'machines': machines }


		print("new_hwconfig_hash:", len(new_hwconfig_hash))
		if selection == 'random':
			items = sorted(new_hwconfig_hash.items(), key=lambda x: random.random())
		elif selection == 'linear':
			items = new_hwconfig_hash.items()

		print("items:", items)
		for k,v in items:
			print("==========================================================")
			machines = v['machines'].copy()
			print("machines:", machines)
			results_train = list()
			results_test = list()
			for i in range(int(nexperiments)):
				print("----------------------------------------------------------")
				train_machines, test_machines = split_machines(machines, hostname_hash, selection)
				(model, result_train) = train_model(train_machines, indir_enc_bm,
									outdir_model, selection, correlation,
									ctype, method, plot_graphs, start, end)
				print('train_test type(model)', type(model))
				results_train.append(result_train)
				if len(test_machines) == 0:
					continue
				(result_test) = test_model(test_machines, indir_enc_bm,
								outdir_model, model, correlation,
								ctype, method, plot_graphs, start, end)
				results_test.append(result_test)
				print("----------------------------------------------------------")
			print_results("train", ctype, results_train)
			if len(test_machines) > 0:
				print_results("test", ctype, results_test)
			print("==========================================================")

def roc_auc_score_multiclass(actual_class, pred_class, average = "macro"):
	unique_class = set(actual_class)
	roc_auc_dict = {}
	for per_class in unique_class:
	#creating a list of all the classes except the current class
		other_class = [x for x in unique_class if x != per_class]

	#marking the current class as 1 and all other classes as 0
		new_actual_class = [0 if x in other_class else 1 for x in actual_class]
		new_pred_class = [0 if x in other_class else 1 for x in pred_class]

	#using the sklearn metrics method to calculate the roc_auc_score
		roc_auc = roc_auc_score(new_actual_class, new_pred_class, average = average)
		roc_auc_dict[per_class] = roc_auc

	return roc_auc_dict

#def print_results(train_test, ctype, ac_list, result, ac_pred_list, roc_auc_list):
def print_results(train_test, ctype, results):
	global nclasses
	if ctype == 'binary' or ctype == 'multi':
		ac_list = [ r['accuracy'] for r in results ]
		ac_pred_list = [ r['class_ac'] for r in results ]
		roc_auc_list = [ r['roc_auc'] for r in results ]

		roc_auc_list_values=[[] for _ in range(nclasses)]
		roc_auc_list_values=[[] for _ in range(nclasses)]

		for i in roc_auc_list:
			for k,v in i.items():
				roc_auc_list_values[k-adj].append(v)

		for i in roc_auc_list:
			for k,v in i.items():
				roc_auc_list_values[k-adj].append(v)

		#print("len(%s_ac)" %(train_test), len(ac_list))
		print("%s_ac" %(train_test), ac_list)
		#print("len(%s_roc_auc_list)" %(train_test), len(roc_auc_list))
		print("%s_roc_auc_list" %(train_test), roc_auc_list)
		if ctype == "binary":
			print("roc_auc_median: { 0: ",median(roc_auc_list_values[0]),
				", 1: ",median(roc_auc_list_values[1])," }")
			print("--------------confusion matrix median -----------------")
			print("       0      1")
		elif ctype == "multi":
			print("%s_roc_auc_median:" %(train_test),
				" { 0: ",median(roc_auc_list_values[0]),
				" , 1: ",median(roc_auc_list_values[1]),
				" , 2: ",median(roc_auc_list_values[2]),
				" , 3: ",median(roc_auc_list_values[3])," }")
			print("--------------confusion matrix median -----------------")
			print("       0      1      2      3")

		for x in range(0,nclasses):
			print(x,end=" ")
			for y in range(0,nclasses):
				temp=list()
				for k in range(0,len(ac_pred_list)):
					temp.append(ac_pred_list[k][y][x])
				abc=round(median(temp),2)
				print("%6.2f"%abc,end=" ")
			print("")
		print("%s_accuracy median" %(train_test), median(ac_list))
	elif ctype == 'reg':
		rmse_list = [ r['rmse'] for r in results ]
		mae_list = [ r['mae'] for r in results ]
		r2_list = [ r['r2'] for r in results ]
		adjr2_list = [ r['adjr2'] for r in results ]

		print("RMSE %s_error median:" %(train_test), median(rmse_list))
		print("MAE %s_error median:" %(train_test), median(mae_list))
		print("R2 %s median" %(train_test), median(r2_list))
		print("AdjR2 %s median" %(train_test), median(adjr2_list))

def split_machines(machines, hostname_hash, selection):
	global nclasses
	global gt
	global adj
	import random
	train_machines = list()
	test_machines = list()
	#   For each machine having the h/w config 'v'
	#	if there are non-zero no of data-samples
	#		read X.csv, and Y.csv for the machine
	#		merge in train_d
	#		remember the machine's enocoded-id in a list 'value'
	#		create dataframe X concat y
	#
	if selection == 'random':
		random.shuffle(machines)
	if len(machines) == 0:
		ed = pd.DataFrame()
		return (ed, ed, ed, ed)

	if (len(machines) == 1):
		trainset_size = 1
	else:
		trainset_size = int(len(machines) * 0.5)

	print('len(machines):', len(machines), 'trainset_size', trainset_size)
	for m in machines:
		# Pickup len(machines) * 0.5 for training
		if len(train_machines) < trainset_size:
			train_machines.append(m)
			print('\ttrain: host:', m, 'len(train_machines):', len(train_machines), 'shape:', hostname_hash[m]['dynamic']['shape'][0])
			#print(m)
		else :  # Pickup remaining len(machines) * 0.5 for testing
			test_machines.append(m)
			print('\ttest: host:', m, 'len(test_machines):', len(test_machines), 'shape:', hostname_hash[m]['dynamic']['shape'][0])
			#print(m)

	print('len(train_machines):', len(train_machines)) #print('value:', train_machines)
	print('len(test_machines):', len(test_machines)) #print('value:', test_machines)

	return train_machines, test_machines

def load_train_data(train_machines, indir, selection, correlation, ctype, plot_graphs):
	global nclasses
	global gt
	global adj
	import random
	train_d = pd.DataFrame()

	for m in train_machines:
		X = pd.read_csv(os.path.join(indir, "%s-X.csv" %(m)))
		y = pd.read_csv(os.path.join(indir, "%s-y.csv" %(m)))
		D = pd.concat([X,y], axis = 1)
		train_d = pd.concat([train_d,D],axis = 0)
		print('\ttrain: host:', m, 'shape:', train_d.shape)

	Xy_train_time = pd.DataFrame(X['time'])
	print("Xy_train_time cols", Xy_train_time.columns)
	#print(train_d['util'].value_counts())
	#print(type(train_d['util'].value_counts()))
	#print('len(value):', len(value))

	#
	#balancing
	#

	# Create small dataframes with class-wise data.
	#print("train_cols",train_d.columns)
	if ctype == 'binary':

		gt = 'util'
		nclasses = 2
		adj = 0
		train_d.drop(columns=['load','time'], axis = 1, inplace = True)
		train_d_la_0 = train_d[train_d.util == 0]
		train_d_la_1 = train_d[train_d.util == 1]
		print("before balancing train value_counts:", train_d['util'].value_counts())

		print("0:", len(train_d_la_0), "1:", len(train_d_la_1))
		mincnt = min(len(train_d_la_0), len(train_d_la_1))
		print('mincnt:', mincnt)
		if mincnt == 0:
			ed = pd.DataFrame()
			return (ed, ed, ed, ed)

		# Randomly sample minimum samples from all classes
		train_d_la_0 = train_d_la_0.sample(mincnt)
		train_d_la_1 = train_d_la_1.sample(mincnt)

		train_d = pd.DataFrame()

		train_d = pd.concat([train_d,train_d_la_0],axis=0)
		train_d = pd.concat([train_d,train_d_la_1],axis=0)

	elif ctype == 'multi':

		gt = 'load'
		nclasses = 4
		adj = 0
		train_d.drop(columns=['util', 'time'], axis = 1, inplace = True)
		train_d_la_0 = train_d[train_d.load == 0]
		train_d_la_1 = train_d[train_d.load == 1]
		train_d_la_2 = train_d[train_d.load == 2]
		train_d_la_3 = train_d[train_d.load == 3]
		print("before balancing train value_counts:", train_d['load'].value_counts())

		print("0:", len(train_d_la_0), "1:", len(train_d_la_1), "2:", len(train_d_la_2), "3:", len(train_d_la_3))
		mincnt = min(len(train_d_la_0), len(train_d_la_1), len(train_d_la_2), len(train_d_la_3))
		print('mincnt:', mincnt)
		if mincnt == 0:
			ed = pd.DataFrame()
			return (ed, ed, ed, ed)

		# Randomly sample minimum samples from all classes
		train_d_la_0 = train_d_la_0.sample(mincnt)
		train_d_la_1 = train_d_la_1.sample(mincnt)
		train_d_la_2 = train_d_la_2.sample(mincnt)
		train_d_la_3 = train_d_la_3.sample(mincnt)

		train_d = pd.DataFrame()

		train_d = pd.concat([train_d,train_d_la_0],axis=0)
		train_d = pd.concat([train_d,train_d_la_1],axis=0)
		train_d = pd.concat([train_d,train_d_la_2],axis=0)
		train_d = pd.concat([train_d,train_d_la_3],axis=0)
	elif ctype == 'reg':
		gt = 'load'
		#train_d.drop(columns=['util', 'time'], axis = 1, inplace = True)
		train_d.drop('util', axis = 1, inplace = True)
		train_d.drop('time', axis = 1, inplace = True)

	if correlation ==  "pearson":
		cor = (train_d.corr(method ='pearson'))
		print("pearson's correlation:")
		print(cor[gt].sort_values(ascending= False))
	elif correlation ==  "spearman":
		cor = (train_d.corr(method ='spearman'))
		print("spearman's correlation:")
		print(cor[gt].sort_values(ascending= False))

	drop_nan_cols = list()
	for k in cor.columns:
		if pd.isnull(cor.iloc[cor.columns.get_loc(gt), cor.columns.get_loc(k)])  and \
		   k not in [ 'power', 'cpu_power', 'inlet_temp', 'util', 'load' ]:
			drop_nan_cols.append(k)

	train_d=train_d.drop(drop_nan_cols,axis = 1)
	#print("load_train_data:", train_d.columns)

	y_train = train_d[gt]
	#X_train = train_d.drop(columns=[gt], axis = 1)
	X_train = train_d.drop(gt, axis = 1)
	y_train = pd.DataFrame(y_train)

	#print('y_train[la].value_counts():', y_train[gt].value_counts())
	plot_data = pd.concat([X,y], axis = 1)
	plot_data.to_csv('%s/%s-train-Xy.csv'%(indir, train_machines[0]), index=False)
	if plot_graphs:
		plt.scatter(X_train['overall_power'], y_train)
		plt.xlabel("overall_power")
		plt.ylabel("cpu_load")
		plt.savefig('%s/%s-benchmark-overallpowervscpuload.png' %(indir, train_machines[0]))
		plt.clf()
		if 'cpu_power' in train_d.columns:
			plt.xlabel("cpu_power")
			plt.ylabel("cpu_load")
			plt.scatter(X_train['cpu_power'], y_train)
			plt.savefig('%s/%s-benchmark-cpupowervscpuload.png' %(indir, train_machines[0]))
			plt.clf()

	return (Xy_train_time, X_train, y_train)

def load_test_data(test_machines, indir, correlation, ctype,  plot_graphs, lower_bound_cpuload, upper_bound_cpuload):
	global nclasses
	global gt
	global adj
	import random
	test_d = pd.DataFrame()
	X_test = pd.DataFrame()
	y_test = pd.DataFrame()

	for m in test_machines:
		X = pd.read_csv(os.path.join(indir, "%s-X.csv" %(m)))
		y = pd.read_csv(os.path.join(indir, "%s-y.csv" %(m)))
		D = pd.concat([X,y], axis = 1)
		test_d = pd.concat([test_d,D],axis = 0)
		print('\ttest: host:', m, 'shape:', test_d.shape)

	Xy_test_time = pd.DataFrame(X['time'])
	print("Xy_test_time cols", Xy_test_time.columns)
	#print(test_d['util'].value_counts())
	#print(type(test_d['util'].value_counts()))
	#print('len(value):', len(value))

	#
	#balancing
	#

	# Create small dataframes with class-wise data.
	#print("test_cols",test_d.columns)
	if ctype == 'binary':

		gt = 'util'
		nclasses = 2
		adj = 0
		test_d.drop(columns=['load','time'], axis = 1, inplace = True)
		print("test util value_counts:", test_d['util'].value_counts())
	elif ctype == 'multi':

		gt = 'load'
		nclasses = 4
		adj = 0
		test_d.drop(columns=['util', 'time'], axis = 1, inplace = True)
		print("test load value_counts:", test_d['load'].value_counts())
	elif ctype == 'reg':
		gt = 'load'
		#test_d.drop(columns=['util', 'time'], axis = 1, inplace = True)
		test_d.drop('util', axis = 1, inplace = True)
		test_d.drop('time', axis = 1, inplace = True)

	if lower_bound_cpuload == 0.0:
		test_d = test_d[(test_d.load>=lower_bound_cpuload) & (test_d.load<=upper_bound_cpuload)]
	else:
		test_d = test_d[(test_d.load>lower_bound_cpuload) & (test_d.load<=upper_bound_cpuload)]
	print("Lower-bound cpuload", lower_bound_cpuload," Upper-bound cpuload", upper_bound_cpuload)
	y_test = test_d[gt]
	#X_test = test_d.drop(columns=[gt], axis = 1)
	X_test = test_d.drop(gt, axis = 1)
	y_test = pd.DataFrame(y_test)
	if correlation ==  "pearson":
		cor = (test_d.corr(method ='pearson'))
		print("pearson's correlation:")
		print(cor[gt].sort_values(ascending= False))
	elif correlation ==  "spearman":
		cor = (test_d.corr(method ='spearman'))
		print("spearman's correlation:")
		print(cor[gt].sort_values(ascending= False))

	plot_data = pd.concat([X,y], axis = 1)
	plot_data.to_csv('%s/%s-test-Xy.csv'%(indir, test_machines[0]), index=False)
	if plot_graphs:
		#plt.xlabel("power")
		plt.xlabel("overall_power")
		plt.ylabel("cpu_load")
		plt.scatter(X_test['overall_power'], y_test)
		plt.savefig('%s/%s-production-overallpowervscpuload.png' %(indir, test_machines[0]))
		plt.clf()
		if 'cpu_power' in test_d.columns:
			plt.xlabel("cpu_power")
			plt.ylabel("cpu_load")
			plt.scatter(X_test['cpu_power'], y_test)
			plt.savefig('%s/%s-production-cpupowervscpuload.png' %(indir, test_machines[0]))
			plt.clf()

	return (Xy_test_time, X_test, y_test)

def train_model(train_machines, indir, outdir, selection, correlation, ctype, method, plot_graphs,start=0,end=2000):
	result_train = dict()

	#mod = LogisticRegression(random_state=0, multi_class='ovr').fit(X_train, y_train)
	#mod = LogisticRegression(random_state=0, multi_class='multinomial').fit(X_train, y_train)
	(Xy_train_time, X_train, y_train) = load_train_data(train_machines, indir, selection, correlation, ctype, plot_graphs)
	if X_train.shape[0] == 0 or y_train.shape[0] == 0:
		return (result_train)

	print("X_train.shape():", X_train.shape)
	print("y_train.shape():", y_train.shape)
	print("train_model: X_train.columns:", X_train.columns)
	print("train_model: y_train.columns:", y_train.columns)
	filename = '%s_%s_model.csv' %(ctype, method)
	bfilename = '%s_%s_model.bin' %(ctype, method)
	if ctype == 'reg':
		t1 = time.time()
		if method == 'lir':
			model = LinearRegression().fit(X_train, y_train)
		elif method == 'rir':
			model = Ridge(alpha =0.1)
			model.fit(X_train, y_train)
		elif method == 'knnr':
			model = KNeighborsRegressor(n_neighbors=11)
			model.fit(X_train, y_train)
		elif method == 'svr_lin':
			model = make_pipeline(StandardScaler(), SVR(C=1.0, kernel='linear'))
			model.fit(X_train, y_train)
		elif method == 'svr_poly':
			model = make_pipeline(StandardScaler(), SVR(C=1.0, kernel='poly'))
			model.fit(X_train, y_train)
		elif method == 'svr_rbf':
			model = make_pipeline(StandardScaler(), SVR(C=1.0, kernel='rbf'))
			model.fit(X_train, y_train)
		t2 = time.time()
		print("Training time for %d samples: %3.3f secs" %(X_train.shape[0], (t2 - t1)))

	else:
		t1 = time.time()
		if method == 'lor':
			#model = LogisticRegression(random_state=0)
			model = LogisticRegression(random_state=0, multi_class='ovr')
			model.fit(X_train, y_train)

			# save the model to disk
			c = X_train.columns.to_numpy()
			c = np.reshape(c, (1,c.shape[0]))
			model_coef = np.append(c, model.coef_, axis = 0)
			np.savetxt(os.path.join(outdir,filename), model_coef, delimiter=',', fmt='%s')

		elif method == 'nbc':
			model = GaussianNB()
			model.fit(X_train, y_train)
		elif method == 'dt':
			'''
			DecisionTreeClassifier(ccp_alpha=0.0, class_weight=None, criterion='gini',
				max_depth=None, max_features=None, max_leaf_nodes=None,
				min_impurity_decrease=0.0, min_impurity_split=None,
				min_samples_leaf=1, min_samples_split=2,
				min_weight_fraction_leaf=0.0, presort='deprecated',
				random_state=30, splitter='best')
			'''
			model = tree.DecisionTreeClassifier(random_state=30)
			model.fit(X_train, y_train)
		elif method == 'rf':
			model = RandomForestClassifier(n_estimators=100, max_depth=40, random_state=30)
			model.fit(X_train, y_train)
			print(model.feature_importances_)

		elif method == 'knn':
			model = KNeighborsClassifier(n_neighbors = 5)
			model.fit(X_train, y_train)
		t2 = time.time()
		print("Training time for %d samples: %3.3f secs" %(X_train.shape[0], (t2 - t1)))

	print("train_model: type(model):", type(model))
	pickle.dump(model, open(os.path.join(outdir,bfilename), 'wb'))

	print('type(model):', type(model))
	score = model.score(X_train, y_train)
	#print("train acc",result*100, "%")
	t1 = time.time()
	y_pred_train = model.predict(X_train)
	t2 = time.time()
	print("Inference time for %d samples: %3.3f secs" %(X_train.shape[0], (t2 - t1)))
	# calculating roc_auc_score on train data
	if ctype == 'binary' or ctype == 'multi':
		result_train['accuracy']  = score
		predicted_class = model.predict(X_train)
		lr_roc_auc_multiclass = roc_auc_score_multiclass(np.ravel(y_train), predicted_class)
		#print("roc_auc_score on train data",lr_roc_auc_multiclass)
		roc_auc_train = lr_roc_auc_multiclass

		train_ac_pred=[[0]*nclasses for i in range(nclasses)]

		for b in range(0,nclasses): # predicted class
			for i in range(0,nclasses): # actual class
				#print("actual:%d predicted:%d" %(i+adj,b+adj))
				training_data = pd.concat([X_train,y_train],axis = 1)
				if ctype == 'binary':
					X_train_Ci = training_data[training_data.util == i]
				elif ctype == 'multi':
					X_train_Ci = training_data[training_data.load == i+adj]
				y_train_Ci = X_train_Ci[gt]
				X_train_Ci = X_train_Ci.drop(gt,axis = 1)
				#print("X_train:", X_train_Ci.shape)

				if X_train_Ci.shape[0] != 0:
					result = model.score(X_train_Ci, y_train_Ci)
					#print("train acc for %d" %(i+adj),result)
					y_pred = model.predict(X_train_Ci)
				else:
					y_pred = [0,0,0,0]

				cnt=0
				for j in range(len(y_pred)):
					if y_pred[j]==b+adj:
						cnt+=1
					rslt = cnt/len(y_pred)
				#print("actual:%d predicted:%d" %(i+adj,b+adj),rslt*100)

				train_ac_pred[b][i]=rslt*100
			#print("\n")
		result_train['roc_auc'] = roc_auc_train
		result_train['class_ac'] = train_ac_pred
		return (model, result_train)
	elif ctype == 'reg':
		result_train['rmse'] = math.sqrt(mean_squared_error(y_train, y_pred_train))
		result_train['mae'] = mean_absolute_error(y_train, y_pred_train)
		result_train['r2']  = score
		result_train['adjr2']  = 1 - (1 - score) * (X_train.shape[0] - 1) / (X_train.shape[0] - X_train.shape[1] - 1)

		plot_data = pd.concat([Xy_train_time, X_train, y_train], axis = 1).rename(columns={"load": "actual_cpu_load"})
		print(type(plot_data))
		plot_data['detected_cpu_load'] = y_pred_train
		#print("train_model: plot_data:", plot_data.columns)
		plot_data.to_csv('%s/%s-train-reg_%s.csv'%(outdir, train_machines[0],method), index=False)
		if plot_graphs:
			p = X_train.columns
			DF = pd.concat([X_train,y_train],axis=1)
			DF = DF[DF[p]>=int(start)]
			DF = DF[DF[p]<=int(end)]
			x = DF['overall_power'] # overall_power
			y = DF['load']
			lw = 0.2
			plt.xlabel("overall_power")
			plt.ylabel("cpuload")
			plt.scatter(x, y, color = 'red', linewidth = lw, marker = '.')
			plt.scatter(x, y, color = 'blue', linewidth = lw, marker = '*')
			plt.savefig('%s/%s-%s-trainvsGT.png' %(indir, ctype, method))
			plt.clf()
		return (model, result_train)


def test_model(test_machines, indir_enc_wl, indir_model, model, correlation, ctype, method, plot_graphs=False, start=0, end=2000,
		 lower_bound_cpuload = 0.0, upper_bound_cpuload = 100.0):
	global adj
	global nclasses
	result_test = dict()

	(Xy_test_time, X_test, y_test) = load_test_data(test_machines, indir_enc_wl, correlation, ctype, plot_graphs, lower_bound_cpuload, upper_bound_cpuload)
	if X_test.shape[0] == 0 or y_test.shape[0] == 0:
		return (result_test)

	print("X_test.shape():", X_test.shape)
	print("y_test.shape():", y_test.shape)
	print("test_model: X_test.columns:", X_test.columns)
	print("test_model: y_test.columns:", y_test.columns)

	score = model.score(X_test, y_test)
	t1 = time.time()
	y_pred_test = model.predict(X_test)
	t2 = time.time()
	print("Inference time for %d samples: %3.3f secs" %(X_test.shape[0], (t2 - t1)))

	if ctype == 'binary' or ctype == 'multi':
		result_test['accuracy']  = score
		# calculating roc_auc_score on test data
		predicted_class = model.predict(X_test)
		print("X_test columns",X_test.columns)
		if plot_graphs:
			ZERO_ZERO = pd.DataFrame()
			ZERO_ONE = pd.DataFrame()
			ONE_ONE = pd.DataFrame()
			ONE_ZERO = pd.DataFrame()

			for i in range(len(predicted_class)):
				if (y_test.iloc[i]['util'] == 0) and (predicted_class[i] == 0):
					ZERO_ZERO = pd.concat([ZERO_ZERO,pd.DataFrame(X_test.iloc[i])],axis =1)
				elif (y_test.iloc[i]['util'] == 1) and (predicted_class[i] == 1):
					ONE_ONE = pd.concat([ONE_ONE,pd.DataFrame(X_test.iloc[i])],axis =1)
				elif (y_test.iloc[i]['util'] == 0) and (predicted_class[i] == 1):
					ZERO_ONE = pd.concat([ZERO_ONE,pd.DataFrame(X_test.iloc[i])],axis =1)
				else:
					ONE_ZERO = pd.concat([ONE_ZERO,pd.DataFrame(X_test.iloc[i])],axis =1)
			print("ZERO_ZERO columns",ZERO_ZERO.columns)
			ZERO_ZERO = ZERO_ZERO.transpose()
			ZERO_ONE = ZERO_ONE.transpose()
			ONE_ONE = ONE_ONE.transpose()
			ONE_ZERO = ONE_ZERO.transpose()

			zz = sns.distplot(ZERO_ZERO['cpu_power'],kde = False)
			zz.set_title('ZERO_ZERO')
			zz.figure.savefig("ZERO_ZERO.png")
			plt.clf()
			oz = sns.distplot(ONE_ZERO['cpu_power'],kde = False)
			oz.set_title('ONE_ZERO')
			oz.figure.savefig("ONE_ZERO.png")
			plt.clf()
			oo = sns.distplot(ONE_ONE['cpu_power'],kde = False)
			oo.set_title('ONE_ONE')
			oo.figure.savefig("ONE_ONE.png")
			plt.clf()
			zo = sns.distplot(ZERO_ONE['cpu_power'],kde = False)
			zo.set_title('ZERO_ONE')
			zo.figure.savefig("ZERO_ONE.png")
			plt.clf()
		lr_roc_auc_multiclass = roc_auc_score_multiclass(np.ravel(y_test), predicted_class)
		#print("roc_auc_score on test data",lr_roc_auc_multiclass)
		roc_auc_test = lr_roc_auc_multiclass

		test_ac_pred=[[0]*nclasses for i in range(nclasses)]

		for b in range(0,nclasses): # predicted class
			for i in range(0,nclasses): # actual class
				testing_data = pd.concat([X_test,y_test],axis = 1)
				if ctype == 'binary':
					X_test_Ci = testing_data[testing_data.util == i]
				elif ctype == 'multi':
					X_test_Ci = testing_data[testing_data.load == i+adj]
				y_test_Ci = X_test_Ci[gt]
				X_test_Ci = X_test_Ci.drop(gt,axis = 1)
				#print("X_test:", X_test_Ci.shape)

				if X_test_Ci.shape[0] != 0:
					result = model.score(X_test_Ci, y_test_Ci)
					#print("test acc for %d"%(i+adj),result)
					y_pred = model.predict(X_test_Ci)
				else:
					y_pred = [0,0,0,0]

				cnt=0
				for j in range(len(y_pred)):
					if y_pred[j]==b+adj:
						cnt+=1
					rslt = cnt/len(y_pred)
				#print("actual:%d predicted:%d" %(i+adj,b+adj),rslt*100)
				#print("\n")
				test_ac_pred[b][i]=rslt*100
			#print("\n")
		result_test['roc_auc'] = roc_auc_test
		result_test['class_ac'] = test_ac_pred
		return (result_test)
	elif ctype == 'reg':
		result_test['rmse'] = math.sqrt(mean_squared_error(y_test, y_pred_test))
		result_test['mae'] = mean_absolute_error(y_test, y_pred_test)
		result_test['r2']  = score
		result_test['adjr2']  = 1 - (1 - score) * (X_test.shape[0] - 1) / (X_test.shape[0] - X_test.shape[1] - 1)

		plot_data = pd.concat([Xy_test_time, X_test, y_test], axis = 1).rename(columns={"load": "actual_cpu_load"})
		plot_data['detected_cpu_load'] = y_pred_test
		#print("test_model: plot_data:", plot_data.columns)
		plot_data.to_csv('%s/%s-test-reg_%s.csv'%(indir_model, test_machines[0],method), index=False)
		if plot_graphs:
			p = X_test.columns
			DF = pd.concat([X_test, y_test],axis=1)
			DF = DF[DF[p]>=int(start)]
			DF = DF[DF[p]<=int(end)]
			x = DF['overall_power'] # overall_power
			y = DF['load']
			lw = 0.2
			y = y_test['load']
			y_pred = model.predict(DF[p])
			plt.xlabel("overall_power")
			plt.ylabel("cpuload")
			plt.scatter(x, y, color = 'red', linewidth = lw, marker = '.')
			plt.scatter(x, y, color = 'blue', linewidth = lw, marker = '*')
			plt.savefig('%s/%s-%s-testvsGT.png' %(indir_enc_wl, ctype, method))
			plt.clf()
		return (result_test)

def test_realdata(args):
	global adj
	# TODO
	indir_cur_inv = os.path.join(args.basedir, "b_curated_inventory")
	indir_enc_inv = os.path.join(args.basedir, "c_encoded_inventory")
	indir_enc_inv_sub = os.path.join(args.basedir, "d_inventory_subset")
	indir_cur_wl = os.path.join(args.basedir, "f_curated_benchmark")
	indir_enc_wl = os.path.join(args.basedir, "g_encoded_benchmark")
	indir_model = os.path.join(args.basedir, "h_model")
	nexperiments = args.nexperiments
	ctype = args.ctype
	method = args.method
	plot_graphs = args.plot_graphs
	# Read & encode features, ground-truth from curated data.
	with open(os.path.join(indir_enc_inv, "encode_hash.json"), "rt") as eh:
		encode_hash = json.load(eh)

	fh = open("%s/machines.json" %(indir_enc_inv), "rt")
	machines_list = json.load(fh)
	fh.close()
	print("len(machines_list):", len(machines_list))

	fh = open("%s/machines_subset_test.json" %(indir_enc_inv_sub), "rt")
	machines_list_sub = json.load(fh)
	fh.close()
	print("len(machines_list_sub):", len(machines_list_sub))
	test_machines = machines_list_sub

	fh = open(os.path.join(indir_enc_wl, "encode_hash.json"), "rt")
	encode_hash = json.load(fh)
	fh.close()

	global nclasses
	global gt
	import random

	if ctype == 'binary':
		gt = 'util'
		nclasses = 2
		adj = 0
	elif ctype == 'multi':
		gt = 'load'
		nclasses = 4
		adj = 0

	filename = '%s_%s_model.csv' %(ctype, method)
	bfilename = '%s_%s_model.bin' %(ctype, method)
	results_test = list()
	model = pickle.load(open(os.path.join(indir_model, bfilename), 'rb'))
	print('train_test type(model)', type(model))
	#print('ctype:', ctype, "nclasses:", nclasses)
	for i in range(int(args.nexperiments)):
		print("----------------------------------------------------------")
		(result_test) = test_model(test_machines, indir_enc_wl,
						indir_model, model, correlation,
						ctype, method, plot_graphs, args.lower_bound_cpuload, args.upper_bound_cpuload)
		results_test.append(result_test)
		print("----------------------------------------------------------")
	if len(test_machines) > 0:
		print_results("test", ctype, results_test)

