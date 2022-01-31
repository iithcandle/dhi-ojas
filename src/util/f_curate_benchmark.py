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
	parser = argparse.ArgumentParser(description='script for curating benchmark data')
	parser.add_argument('--dircuratedinv', help='directory to read curated inventory data')
	parser.add_argument('--direncodedinv', help='directory to read enocded inventory data')
	parser.add_argument('--dirinvsub', help='directory to read subset of inventory data')
	parser.add_argument('--dirrawdata', help='directory to read the raw benchmark/production measurement data')
	parser.add_argument('--dircurateddata', help='directory to read the curated benchmark/production measurement data')
	parser.add_argument('--wtype', default='production', choices=['benchmark', 'production'], help='type of workload (benchmark or production)')
	parser.add_argument('--drift_interval', default = 0.0, help='drift interval according to the machines sampling interval')
	parser.add_argument('--workload', action='append', default=[],
			choices=['nascent_idle_benchmark', 'nascent_cpu_benchmark', 'nascent_memory_benchmark',
				'nascent_gpu_benchmark', 'nascent_disk_benchmark', 'nascent_network_benchmark',
				'nascent_sleep_cpu_benchmark', 'nascent_quick_test', 'real'],
			 help='type of benchmark to be run')

	args = parser.parse_args()
	print(args)

	# Plant a signal handler for Ctrl+C
	signal.signal(signal.SIGINT, sigint_handler)

	if not args.dirrawdata:
		print("must pass --dirrawdata")
		sys.exit(1)

	if not os.path.isdir(args.dirrawdata):
		print(args.dirrawdata, " does not exist")
		sys.exit(1)

	if not args.dircuratedinv:
		args.dircuratedinv = os.path.join(args.dirrawdata, "..", "b_curated_inventory")

	if not os.path.isdir(args.dircuratedinv):
		print(args.dircuratedinv, " does not exist")
		sys.exit(1)

	if not args.direncodedinv:
		args.direncodedinv = os.path.join(args.dirrawdata, "..", "c_encoded_inventory")

	if not os.path.isdir(args.direncodedinv):
		print(args.direncodedinv, " does not exist")
		sys.exit(1)

	if not args.dirinvsub:
		args.dirinvsub = os.path.join(args.dirrawdata, "..", "d_inventory_subset")

	if not os.path.isdir(args.dirinvsub):
		print(args.dirinvsub, " does not exist")
		sys.exit(1)

	if not args.dircurateddata:
		if args.wtype == "benchmark":
			args.dircurateddata = os.path.join(args.dirrawdata, "..", "f_curated_benchmark")
		elif args.wtype == "production":
			args.dircurateddata = os.path.join(args.dirrawdata, "..", "f_curated_production")

	os.makedirs(args.dircurateddata, exist_ok=True)

	my_dhiojas_lib.curate_measurement_data(args.dircuratedinv, args.direncodedinv, args.dirinvsub, args.dirrawdata, args.dircurateddata, args.wtype, float(args.drift_interval), args.workload)

	sys.exit(0)

