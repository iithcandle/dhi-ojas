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
	parser.add_argument('--direncoded', help='directory to save enocded the encoded data')
	parser.add_argument('--direncoded_subset', help='directory to save encoded the data with feasible machines')

	args = parser.parse_args()
	print(args)

	# Plant a signal handler for Ctrl+C
	signal.signal(signal.SIGINT, sigint_handler)

	# Read encoded machines info from encoded directory.
	if not os.path.isdir(args.direncoded):
		print(args.direncoded, " does not exist")
		sys.exit(1)

	if not args.direncoded_subset:
		args.direncoded_subset = os.path.join(args.direncoded, "..", "d_inventory_subset")

	os.makedirs(args.direncoded_subset, exist_ok=True)

	# Threads dont work, as asyncio has per-process global data structures.
	# Create separate process for encoding data
	ced_job = multiprocessing.Process(target = my_dhiojas_lib.find_feasible_subset, args = (args.direncoded, args.direncoded_subset), daemon=True)

	# start the child processes
	ced_job.start()

	# wait for the children to join back
	ced_job.join()

	sys.exit(0)

