#!/usr/bin/env python3

#
# Copyright (C) 2018-2022 Maruthi Seshidhar Inukonda - All Rights Reserved.
# maruthi.inukonda@gmail.com
#
# This file is released under the Affero GPLv3 License.
#
import argparse
import signal
import sys
import pytz
from datetime import datetime,timedelta,timezone
import json
import pprint

import threading
import multiprocessing
import subprocess
import os
import io

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split

def sigint_handler(signum, frame):
	print('INT Signal handler called with signal', signum)
	sys.exit(0)


if __name__ == "__main__":
	sys.path.append('../lib/')
	sys.path.append('/usr/local/lib/python3.6/dist-packages/dhi-ojas/')
	import my_dhiojas_lib

	# Parse the command line arguments
	parser = argparse.ArgumentParser(description='script for encoding data from benchmarks')
	parser.add_argument('--dircuratedinv', help='directory to read curated inventory data')
	parser.add_argument('--direncodedinv', help='directory to read enocded inventory data')
	parser.add_argument('--dirinvsub', help='directory to read subset of inventory data')
	parser.add_argument('--dircurateddata', help='directory to read the curated benchmark/production measurement data')
	parser.add_argument('--direncodeddata', help='directory to save the encoded benchmark/production measurement data')
	parser.add_argument('--wtype', default='production', choices=['benchmark', 'production'], help='type of workload (benchmark or production)')
	parser.add_argument('--encode', default=True, action='store_true', help='option to encode data into numpy/panda format')
	parser.add_argument('--encoding_hostname', default='label', help='encoding type of hostname (1-hot or label)')
	parser.add_argument('--encoding_inlet_temp', default=None, help='encoding type of inlet_temp (None, as-is)')
	parser.add_argument('--encoding_cpuload', default='as-is', help='encoding type of cpuload (class, as-is)')
	parser.add_argument('--encoding_fans_speed', default=None, help='encoding type of fans speed (None, as-is)')
	parser.add_argument('--encoding_cpu_power', default=None, help='encoding type of cpu power (None, as-is)')
	parser.add_argument('--encoding_fan_power', default=None, help='encoding type of fan power (None, as-is)')
	parser.add_argument('--encoding_systemboard_power', default=None, help='encoding type of systemboard power (None, as-is)')
	parser.add_argument('--encoding_hdd_power', default=None, help='encoding type of hdd power (None, as-is)')
	parser.add_argument('--encoding_overall_power', default='as-is', help='encoding type of cpu power (None, as-is, host)')
	parser.add_argument('--cpuload_threshold', default=0.0, help='cpuload threshold value')
	parser.add_argument('--maxloadavg', default=80, help='max loadavg value to remove samples as out-liers')
	parser.add_argument('--include_timestamp', default=False, action='store_true', help='flag to include timestamp in X.csv y.csv')
	parser.add_argument('--debug', default=False, action='store_true', help='flag to generate intermediate data as files')

	args = parser.parse_args()
	print(args)

	# Plant a signal handler for Ctrl+C
	signal.signal(signal.SIGINT, sigint_handler)

	if not args.dircurateddata:
		print("must pass --dircurateddata")
		sys.exit(1)

	if not os.path.isdir(args.dircurateddata):
		print(args.dircurateddata, " does not exist")
		sys.exit(1)

	if not args.dircuratedinv:
		args.dircuratedinv = os.path.join(args.dircurateddata, "..", "b_curated_inventory")

	if not os.path.isdir(args.dircuratedinv):
		print(args.dircuratedinv, " does not exist")
		sys.exit(1)

	if not args.direncodedinv:
		args.direncodedinv = os.path.join(args.dircurateddata, "..", "c_encoded_inventory")

	if not os.path.isdir(args.direncodedinv):
		print(args.direncodedinv, " does not exist")
		sys.exit(1)

	if not args.dirinvsub:
		args.dirinvsub = os.path.join(args.dircurateddata, "..", "d_inventory_subset")

	if not args.direncodeddata:
		if args.wtype == "benchmark":
			args.direncodeddata = os.path.join(args.dircurateddata, "..", "g_encoded_benchmark")
		elif args.wtype == "production":
			args.direncodeddata = os.path.join(args.dircurateddata, "..", "g_encoded_production")

	os.makedirs(args.direncodeddata, exist_ok=True)

	my_dhiojas_lib.encode_data(args.dircuratedinv, args.direncodedinv, args.dirinvsub, args.dircurateddata,
				args.wtype, args.direncodeddata,
				encoding_inlet_temp=args.encoding_inlet_temp,
				encoding_fans_speed=args.encoding_fans_speed,
				cpuload_threshold=float(args.cpuload_threshold),
				encoding_cpu_power = args.encoding_cpu_power,
				encoding_fan_power = args.encoding_fan_power,
				encoding_systemboard_power = args.encoding_systemboard_power,
				encoding_hdd_power = args.encoding_hdd_power,
				encoding_overall_power=args.encoding_overall_power,
				encoding_cpuload = args.encoding_cpuload)

	sys.exit(0)

