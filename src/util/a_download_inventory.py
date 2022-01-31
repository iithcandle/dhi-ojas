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
import xml.etree.ElementTree as ET
import xmltodict
import re
from dateutil.parser import parse

def sigint_handler(signum, frame):
	print('INT Signal handler called with signal', signum)
	sys.exit(0)

if __name__ == "__main__":
	now = datetime.now()
	timestamp = now.strftime("%Y%m%d_%H%M%S")

	# Parse the command line arguments
	parser = argparse.ArgumentParser(description='script for training data collection')
	parser.add_argument('--dirraw', default="data/%s/a_raw_inventory" %(timestamp), help='directory to download raw inventory data')

	args = parser.parse_args()
	#print(args)

	# Plant a signal handler for Ctrl+C
	signal.signal(signal.SIGINT, sigint_handler)

	sys.path.append('/usr/local/lib/python3.6/dist-packages/dhi-ojas/')
	sys.path.append('../lib/')
	import my_dhiojas_lib

	os.makedirs(args.dirraw, exist_ok=True)

	# Threads dont work, as asyncio has per-process global data structures.
	# Create separate process for downloading inventory data
	cid_job = multiprocessing.Process(target = my_dhiojas_lib.download_inventory_data, args = (args.dirraw,), daemon=True)

	# start the child processes
	cid_job.start()

	# wait for the children to join back
	cid_job.join()

	sys.exit(0)

