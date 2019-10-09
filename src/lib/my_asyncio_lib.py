#!/usr/bin/env python3

#
# Copyright (C) 2018-2019 Maruthi Seshidhar Inukonda - All Rights Reserved.
# maruthi.inukonda@gmail.com
#
# This file is released under the GPLv3 License.
#

import asyncio
import subprocess

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
		print(
			"Failed:", *cmd, "pid=%s, result: %s"
			%(process.pid, stderr.decode().strip()),
			flush=True,
		)

	# Result
	result = stdout.decode().strip()

	# Return stdout
	return result

def run_cmds_last(loop, hosts):
	cmds = []
	#print("hosts:", hosts)
	for h in hosts:
		cmds.append(['ssh', '-o', 'StrictHostKeyChecking=no',
                    '-o', 'UserKnownHostsFile=/dev/null',
                    '-i', '~cs18resch01001/.ssh/id_rsa',
	            'owner@%s' %(h['ip_address']), 'last', '-s', '-1days'])

	futures = [call_cmd(*cmd) for cmd in cmds]
	# Get the async functions' results (a tuple having sets)
	results = loop.run_until_complete(asyncio.wait(futures))
	#login_count = list(range(0, len(results[0])))
	# set#0 contains the results.
	login_count = [0] * len(results[0])
	# Iterate over each element in the set to get individual results
	for k in range(0, len(futures)):
		cmd = futures[k]
		for id,val in enumerate(results[0]):
			if val._coro == cmd:
				#print("found id:", id, " val:", val)
				#print(val.result())
				out = val.result().splitlines()
				for line in out:
					#print(line)
					token = line.split()
					#print("token:", token)
					if len(token) == 0:
						continue
					if 'pts' in token[1] or 'tty' in token[1]:
						login_count[k] += 1
				break
	return login_count

def run_cmds_uptime(loop, hosts):
	cmds = []
	#print("hosts:", hosts)
	for h in hosts:
		cmds.append(['ssh', '-o', 'StrictHostKeyChecking=no',
                    '-o', 'UserKnownHostsFile=/dev/null',
                    '-i', '~cs18resch01001/.ssh/id_rsa',
                    'owner@%s' %(h['ip_address']), 'uptime'])

	futures = [call_cmd(*cmd) for cmd in cmds]
	# Get the async functions' results (a tuple having sets)
	results = loop.run_until_complete(asyncio.wait(futures))
	#usage_prcnt = list(range(0, len(results[0])))
	# set#0 contains the results.
	usage_prcnt = [0] * len(results[0])
	# Iterate over each element in the set to get individual results
	for k in range(0, len(futures)):
		cmd = futures[k]
		for id,val in enumerate(results[0]):
			if val._coro == cmd:
				#print("found id:", id, " val:", val)
				#print(val.result())
				token = val.result().split('load average:')
				if len(token) != 0:
					usage_prcnt[k] = token[1].split(',')[1]
					#print('usage_prcnt', usage_prcnt[k])
				#print("token:", token)
				break
	return usage_prcnt

