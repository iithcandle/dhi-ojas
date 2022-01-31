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
	parser = argparse.ArgumentParser(description='script for enoding training data')
	parser.add_argument('--encode', default=True, action='store_true', help='option to encode data into numpy/panda format')
	parser.add_argument('--encoding_hostname', default='label', help='encoding type of hostname (1-hot or label)')
	parser.add_argument('--encoding_system_vendor', default='1-hot', help='encoding type of system_vendor (1-hot or label)')
	parser.add_argument('--encoding_system_product', default='1-hot', help='encoding type of system_product (1-hot or label)')
	parser.add_argument('--encoding_processor_vendor', default='1-hot', help='encoding type of processor_vendor (1-hot or label)')
	parser.add_argument('--encoding_processor_product', default='1-hot', help='encoding type of processor_product (1-hot or label)')
	parser.add_argument('--encoding_accelerators', default='n-hot', help='encoding type of accelerators (n-hot)')
	parser.add_argument('--encoding_disks', default='n-hot', help='encoding type of disks (n-hot)')
	parser.add_argument('--encoding_nics', default='n-hot', help='encoding type of nics (n-hot)')
	parser.add_argument('--dircurated', help='directory from which to read the curated data')
	parser.add_argument('--direncoded', help='directory to save enocded the curated data')
	parser.add_argument('--debug', default=False, action='store_true', help='flag to generate intermediate data as files')

	args = parser.parse_args()
	print(args)

	if not args.direncoded:
		args.direncoded = os.path.join(args.dircurated, "..", "c_encoded_inventory")

	# Plant a signal handler for Ctrl+C
	signal.signal(signal.SIGINT, sigint_handler)

	# Read raw machines info from downloaded directory.
	if not os.path.isdir(args.dircurated):
		print(args.dircurated, " does not exist")
		sys.exit(1)

	os.makedirs(args.direncoded, exist_ok=True)

	# Threads dont work, as asyncio has per-process global data structures.
	# Create separate process for encoding data
	ced_job = multiprocessing.Process(target = my_dhiojas_lib.encode_inventory_data, args = (args.dircurated, args.direncoded, args), daemon=True)

	# start the child processes
	ced_job.start()

	# wait for the children to join back
	ced_job.join()

	sys.exit(0)

