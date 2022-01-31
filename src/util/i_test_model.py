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
	parser = argparse.ArgumentParser(description='script for generating model')
	parser.add_argument('--basedir', default="data/latest", help='directory have dataset')
	parser.add_argument('--method', default="lor", help='model to be used (lor/dt/rf/nbc/lir/svr/rir/knnr)')
	parser.add_argument('--nexperiments', default=1, help='number of experiments of train/test accuracy to be done and find median of them')
	parser.add_argument('--ctype', default='binary', help='option to specify classification type (binary or multi or reg)')
	parser.add_argument('--plot_graphs', default=False, action='store_true', help='option to plot graphs for classification and regression')
	args = parser.parse_args()
	print(args)

	# Plant a signal handler for Ctrl+C
	signal.signal(signal.SIGINT, sigint_handler)

	if not os.path.isdir(args.basedir):
		print(args.basedir, " does not exist")
		sys.exit(1)

	my_dhiojas_lib.test_realdata(args)

	sys.exit(0)

