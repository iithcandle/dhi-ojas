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
	parser = argparse.ArgumentParser(description='script for collecting data from production systems')
	parser.add_argument('--direncodedinv', help='directory to read enocded inventory data')
	parser.add_argument('--dirinvsub', help='directory to read subset of inventory data')
	parser.add_argument('--dirrawdata', help='directory to save the benchmark raw data')
	parser.add_argument('--skip_host', default=False, action='store_true', help='skip host data collection')
	parser.add_argument('--skip_bmc', default=False, action='store_true', help='skip BMC data collection')
	parser.add_argument('--bmc_type', default='closed', help='closed or open')

	args = parser.parse_args()
	print(args)

	# Plant a signal handler for Ctrl+C
	signal.signal(signal.SIGINT, sigint_handler)

	if not args.dirrawdata:
		print("must pass --dirrawdata")
		sys.exit(1)

	os.makedirs(args.dirrawdata, exist_ok=True)

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

	my_dhiojas_lib.collect_realdata(args.direncodedinv, args.dirinvsub, args.dirrawdata, "real", args.skip_host, args.skip_bmc, args.bmc_type)

	sys.exit(0)

