#!/usr/bin/env python3

#
# Copyright (C) 2018-2022 Maruthi Seshidhar Inukonda - All Rights Reserved.
# maruthi.inukonda@gmail.com
#
# This file is released under the Affero GPLv3 License.
#
import argparse
import os
import json
import sys
import pandas as pd
from datetime import datetime,timedelta,timezone
import numpy as np
import matplotlib.pyplot as plt
from statistics import median,mean,stdev,mode

hostname = os.path.basename(sys.argv[1]).split('-')[0]
hostname = os.path.basename(sys.argv[1]).split('-')[0]

# Pass in the curated json which contains inner-joined host_data and bmc_data.
#host_data = pd.read_json(sys.argv[1])
fh = open(sys.argv[1])
data = json.load(fh)
fh.close()

mat = list()
for k,v in data.items():
	if v['cpuload'] < 0:
		continue
	if v['power'] < 0 or v['util'] < 0:
		continue
	if 'inlet_temp' not in v:
		print(k, v)
	if v['inlet_temp'] < 0:
		continue
	if 'cpu_power' in v and v['cpu_power'] < 0:
		continue
	#print(k, ":", v)
	row  = { "time": datetime.strptime(k, '%Y-%m-%d %H:%M:%S.%f').timestamp(),
		"cpuload": v['cpuload'],
		"power": v['power'],
		"cpu_power": v['cpu_power'],
		"inlet_temp" : v['inlet_temp'],
		"exhaust_temp" : v['exhaust_temp'],
		"mem_util" : v['mem_util'],
		#"net_util" : sum(v['net_util']),
		#"disk_iops" : sum(v['disk_iops']),
		}
	mat.append(row)

host_data = pd.DataFrame(mat)
print("Total data:", host_data.columns, host_data.shape)

print(host_data.columns)

x = host_data['time']
#print("type(x):", type(x))

lw = 0.2
mrk = '.'

x = host_data['time']

y = host_data['power']
plt.xlabel("time")
plt.ylabel("power")
plt.scatter(x, y, color='red', linewidth=lw, label='power', marker=mrk)
plt.savefig('%s-power-xy.png' %(hostname), dpi=300) #bbox_inches='tight')
plt.clf()

y = host_data['cpuload']
plt.ylabel("cpuload")
plt.scatter(x, y, color='blue', linewidth=lw, label='cpuload', marker=mrk)
plt.savefig('%s-cpuload-xy.png' %(hostname), dpi=300) #bbox_inches='tight')
plt.clf()

y = host_data['cpu_power']
plt.ylabel("cpu_power")
plt.scatter(x, y, color='indigo', linewidth=lw, label='cpu_power', marker=mrk)
plt.savefig('%s-cpupower-xy.png' %(hostname), dpi=300) #bbox_inches='tight')
plt.clf()

y = host_data['mem_util']
plt.ylabel("mem_util")
plt.scatter(x, y, color='green', linewidth=lw, label='mem_util', marker=mrk)
plt.savefig('%s-memutil-xy.png' %(hostname), dpi=300) #bbox_inches='tight')
plt.clf()

'''
y = host_data['net_util']
plt.ylabel("net_util")
plt.scatter(x, y, color='magenta', linewidth=lw, label='net_util', marker=mrk)
plt.savefig('%s-netutil-xy.png' %(hostname), dpi=300) #bbox_inches='tight')
plt.clf()

y = host_data['disk_iops']
plt.ylabel("disk_iops")
plt.scatter(x, y, color='orange', linewidth=lw, label='disk_iops', marker=mrk)
plt.savefig('%s-diskiops-xy.png' %(hostname), dpi=300) #bbox_inches='tight')
plt.clf()
'''

y = host_data['inlet_temp']
plt.ylabel("inlet_temp")
plt.scatter(x, y, color='purple', linewidth=lw, label='inlet_temp', marker=mrk)
plt.savefig('%s-inlet_temp-xy.png' %(hostname), dpi=300) #bbox_inches='tight')
plt.clf()

y = host_data['exhaust_temp']
plt.ylabel("exhaust_temp")
plt.scatter(x, y, color='brown', linewidth=lw, label='exhaust_temp', marker=mrk)
plt.savefig('%s-exhaust_temp-xy.png' %(hostname), dpi=300) #bbox_inches='tight')
plt.clf()

#host_data = pd.DataFrame.from_dict(dict_train, orient='index')
range_list = [[0,20], [20,40], [40,60], [60,80], [80,100]]

for i in range(0, 5):
	if i == 0:
		ci = host_data[(host_data.cpuload <= range_list[i][1])]
	else:
		temp = host_data[(host_data.cpuload > range_list[i][0])].copy()
		ci = temp[(temp.cpuload<=range_list[i][1])]
	print("For class:", i, " Nsamples:", len(ci),
		"Power:: Min:", ci['power'].min(axis=0),
		" Max:", ci['power'].max(axis=0),
		" Median:", ci['power'].median(axis=0),
		" StdDev:", ci['power'].std(axis=0),
		"CPU Power:: Min:", ci['cpu_power'].min(axis=0),
		" Max:", ci['cpu_power'].max(axis=0),
		" Median:", ci['cpu_power'].median(axis=0),
		" StdDev:", ci['cpu_power'].std(axis=0))
	'''
	x = ci['time']
	y = ci['power']
	plt.xlabel("time")
	plt.ylabel("power")
	plt.scatter(x, y, color='red', linewidth=lw, label='power', marker=mrk)
	#plt.plot(x, y, color='red', linewidth=lw, linestyle='dotted', label='power')
	plt.savefig('%s-power-c%d-xy.png' %(hostname, i), dpi=300) #bbox_inches='tight')
	plt.clf()

	y = ci['cpuload']
	plt.ylabel("cpuload")
	plt.scatter(x, y, color='blue', linewidth=lw, label='cpuload', marker=mrk)
	#plt.plot(x, y, color='blue', linewidth=lw, linestyle='dashed', label='cpuload')
	plt.savefig('%s-cpuload-c%d-xy.png' %(hostname, i), dpi=300) #bbox_inches='tight')
	plt.clf()

	y = ci['cpupower']
	plt.ylabel("cpupower")
	plt.scatter(x, y, color='indigo', linewidth=lw, label='cpupower', marker=mrk)
	plt.savefig('%s-cpupower-c%d-xy.png' %(hostname, i), dpi=300) #bbox_inches='tight')
	plt.clf()

	y = ci['mem_util']
	plt.ylabel("mem_util")
	plt.scatter(x, y, color='green', linewidth=lw, label='mem_util', marker=mrk)
	#plt.plot(x, y, color='green', linewidth=lw, linestyle='dashed', label='mem_util')
	plt.savefig('%s-memutil-c%d-xy.png' %(hostname, i), dpi=300) #bbox_inches='tight')
	plt.clf()

	y = ci['net_util']
	plt.ylabel("net_util")
	plt.scatter(x, y, color='magenta', linewidth=lw, label='net_util', marker=mrk)
	#plt.plot(x, y, color='black', linewidth=lw, linestyle='dashed', label='net_util')
	plt.savefig('%s-netutil-c%d-xy.png' %(hostname, i), dpi=300) #bbox_inches='tight')
	plt.clf()

	y = ci['disk_iops']
	plt.ylabel("disk_iops")
	plt.scatter(x, y, color='orange', linewidth=lw, label='disk_iops', marker=mrk)
	#plt.plot(x, y, color='orange', linewidth=lw, linestyle='dashed', label='disk_iops')
	plt.savefig('%s-diskiops-c%d-xy.png' %(hostname, i), dpi=300) #bbox_inches='tight')
	plt.clf()
	#print("power, cpuload plot for %s c%d saved" %(hostname, i))
	'''

print("detailed plots for %s c[0-3] saved" %(hostname))

