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

def sigint_handler(signum, frame):
	print('INT Signal handler called with signal', signum)
	sys.exit(0)


if __name__ == "__main__":
	sys.path.append('../lib/')
	sys.path.append('/usr/local/lib/python3.6/dist-packages/dhi-ojas/')
	import my_dhiojas_lib

	# Parse the command line arguments
	parser = argparse.ArgumentParser(description='script for generating model')
	parser.add_argument('--dircuratedinv', help='directory to read curated inventory data')
	parser.add_argument('--direncodedinv', help='directory to read enocded inventory data')
	parser.add_argument('--direncodedtraindata', help='directory containing encoded csv files of training dataset')
	parser.add_argument('--direncodedtestdata', help='directory containing encoded csv files of test dataset')
	parser.add_argument('--dirinvsub', help='directory to read subset of inventory data')
	parser.add_argument('--trainmachine', action='append', default=[], help='machine name for training')
	parser.add_argument('--testmachine', action='append', default=[], help='machine name for testing')
	parser.add_argument('--dirmodel', help='directory to save the model')
	parser.add_argument('--method', default="svr_rbf", help='model to be used', choices=['lor', 'dt', 'rf', 'nbc', 'lir', 'rir', 'knnr', 'svr_lin', 'svr_poly', 'svr_rbf'])
	parser.add_argument('--nexperiments', default=1, help='number of experiments of train/test accuracy to be done and find median of them')
	parser.add_argument('--selection', default='random', help='option to specify selection criterion to pickup machines for train and test (linear or random)')
	parser.add_argument('--ctype', default='binary', help='option to specify classification type (binary or multi or reg)')
	parser.add_argument('--correlation', default='pearson', help='option to specify correlation function for feature selection (spearman or pearson)')
	parser.add_argument('--plot_graphs', default=False, action='store_true', help='option to plot graphs for classification and regression')
	parser.add_argument('--lower_bound_cpuload', default=float(0.0), help='option to specify lower bound cpuload')
	parser.add_argument('--upper_bound_cpuload', default=float(100.0), help='option to specify upper bound cpuload')
	parser.add_argument('--start', default=0, help='cpu_power lower bound in plots')
	parser.add_argument('--end', default=2500, help='cpu_power uppper bound in plots')


	args = parser.parse_args()
	print(args)

	# Plant a signal handler for Ctrl+C
	signal.signal(signal.SIGINT, sigint_handler)

	if not args.direncodedtraindata:
		print(args.direncodedtraindata, "encoded training data directory is required")
		sys.exit(1)

	if not os.path.isdir(args.direncodedtraindata):
		print(args.direncodedtraindata, " does not exist")
		sys.exit(1)

	if args.direncodedtestdata and not os.path.isdir(args.direncodedtestdata):
		args.direncodedtestdata = os.path.join(args.direncodedtraindata, "..", "g_encoded_production")
		print(args.direncodedtestdata, " does not exist")
		sys.exit(1)

	if not args.dircuratedinv:
		args.dircuratedinv = os.path.join(args.direncodedtraindata, "..", "b_curated_inventory")

	if not os.path.isdir(args.dircuratedinv):
		print(args.dircuratedinv, " does not exist")
		sys.exit(1)

	if not args.direncodedinv:
		args.direncodedinv = os.path.join(args.direncodedtraindata, "..", "c_encoded_inventory")

	if not os.path.isdir(args.direncodedinv):
		print(args.direncodedinv, " does not exist")
		sys.exit(1)

	if not args.dirinvsub:
		args.dirinvsub = os.path.join(args.direncodedtraindata, "..", "d_inventory_subset")

	if not os.path.isdir(args.dirinvsub):
		print(args.dirinvsub, " does not exist")
		sys.exit(1)


	if not args.dirmodel:
		args.dirmodel = os.path.join(args.direncodedtraindata, "..", "h_model")

	os.makedirs(args.dirmodel, exist_ok=True)

	my_dhiojas_lib.generate_model(args.direncodedinv, args.dirinvsub,
			args.direncodedtraindata, args.trainmachine,
			args.direncodedtestdata, args.testmachine,
			args.selection, args.correlation, args.nexperiments,
			args.ctype, args.method, args.dirmodel, args.plot_graphs, args.start, args.end,
			float(args.lower_bound_cpuload), float(args.upper_bound_cpuload))

	sys.exit(0)

