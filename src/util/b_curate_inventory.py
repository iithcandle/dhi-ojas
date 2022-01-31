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
	sys.path.append('/usr/local/lib/python3.6/dist-packages/dhi-ojas/')
	sys.path.append('../lib/')
	import my_maas_lib
	import my_dhiojas_lib

	# Parse the command line arguments
	parser = argparse.ArgumentParser(description='script for curating inventory data')
	parser.add_argument('--dirraw', required = True, help='directory where raw inventory data is found')
	parser.add_argument('--dircurated', help='directory to save curated inventory data')

	args = parser.parse_args()
	#print(args)

	# Plant a signal handler for Ctrl+C
	signal.signal(signal.SIGINT, sigint_handler)

	# Read raw machines info from downloaded directory.
	if not os.path.isdir(args.dirraw):
		print(args.dirraw, " does not exist")
		sys.exit(1)

	if args.dircurated == None:
		args.dircurated = os.path.join(args.dirraw, "..", "b_curated_inventory")

	os.makedirs(args.dircurated, exist_ok=True)
	fh = open("%s/machines.json" %(args.dirraw), "rt")
	ret = fh.read()
	fh.close()
	machines_list = json.loads(ret)
	print("len(machines_list):", len(machines_list))

	compat = dict()
	# Threads dont work, as asyncio has per-process global data structures.
	# Create separate process for downloading inventory data
	cid_job = multiprocessing.Process(target = my_dhiojas_lib.curate_inventory_data, args = (machines_list, args.dirraw, args.dircurated, compat), daemon=True)

	# start the child processes
	cid_job.start()

	# wait for the children to join back
	cid_job.join()

	sys.exit(0)

