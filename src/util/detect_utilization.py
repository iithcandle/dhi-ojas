#!/usr/bin/env python3

#
# Copyright (C) 2018-2021 Maruthi Seshidhar Inukonda - All Rights Reserved.
# maruthi.inukonda@gmail.com
#
# This file is released under the Affero GPLv3 License.
#

import argparse
import signal
import sys
import pytz
from datetime import datetime,timedelta,timezone
sys.path.append('/usr/local/lib/python3.6/dist-packages/dhi-ojas/')
import my_maas_lib
import my_gnocchi_lib

import smtplib
import email.message

import threading
import multiprocessing
import json
import yaml
import io

def sigint_handler(signum, frame):
	print('INT Signal handler called with signal', signum)
	sys.exit(0)

regctrl = my_maas_lib.regctrl_url

def detect_under_utilization(interval):
	user_list = my_maas_lib.get_users()
	users = {}
	for user in user_list:
		users[user['username']] = user
	#print("len(users):", len(users))
	#print("users:", users)

	# Iterate over maas machines and create a hash indexed by hostname.
	# Also create a hash indexed by owner.
	ret = my_maas_lib.get_machines()
	machines_list = json.loads(ret)
	hosts =[]
	machines_hash = dict()
	users_machines_hash = dict()
	for mach in machines_list:
		# Only deployed machines could have agent running.
		#if mach['status_name'] != "Deployed":
		#	continue
		# Only powered on systems' agent is reachable.
		#if mach['power_state'] != 'on':
		#	continue
		#print("\n")
		#print("mach:", mach)
		#print("hostname:", mach['hostname'])
		#print("status_name:", mach['status_name'])
		if mach['owner'] not in users_machines_hash:
			users_machines_hash[mach['owner']] = []
		m = {
			'hostname' : mach['hostname'],
			'system_id' : mach['system_id'],
			'owner' : mach['owner'],
			'resource_uri' : mach['resource_uri'], # resource_uri in maas restapi
			'resource' : ""  # resource in gnocchi restapi
		}
		machines_hash[mach['hostname']] = m
		users_machines_hash[mach['owner']].append(m)

	util_off_count = 0
	util_unknown_count = 0
	util_error_count = 0
	util_zero_count = 0
	util_nonzero_count = 0
	pwr_off_avg = 0
	pwr_unknown_avg = 0
	pwr_util_avg = 0
	pwr_unutil_avg = 0

	# Iterate over gnocchi resources and create an hash index to objects
	# in machines_hash.
	resources = my_gnocchi_lib.get_resources()
	for r in resources:
		hostname = r['original_resource_id'].split(':')[1]
		if hostname in machines_hash:
			machines_hash[hostname]['resource'] = r
	#print("len(machines_hash):", len(machines_hash))
	#print("machines_hash:", machines_hash)
	#print("len(users_machines_hash):", len(users_machines_hash))
	#print("users_machines_hash", users_machines_hash)

	# For all underutilized machines belonging to a user, send email
	machine_count = 0
	with open("/etc/dhi-ojas/email.yml", 'r') as stream:
		email_config = yaml.safe_load(stream)['email']

	# creates SMTP session
	s = smtplib.SMTP(email_config['smtpserver'], email_config['port'])

	# start TLS for security
	s.ehlo()
	s.starttls()

	# Authentication
	s.login(email_config['emailid'], email_config['appkey'])

	for user,mlist in users_machines_hash.items():
		if user is None:
			continue
		send_flag = False
		msg = email.message.Message()
		# compose message to be sent
		msg['Subject'] = 'Under utilization alert'
		msg['From'] = email_config['emailid']
		#msg['To'] = users[user]["email"]
		msg['To'] = 'cs18resch01001@iith.ac.in'
		msg.add_header('Content-Type','text/html')
		message = "\nDear %s,<br><br>" %(user)
		message += "The following machines are under utilized.<br><br>"
		for mach in mlist:
			#print("machine:", mach['hostname'])
			# Check under utilization
			utilized = None
			login_count = -1 # Login count in last 1 day
			start_tm = None
			for mn,mid in machines_hash[mach['hostname']]['resource']['metrics'].items(): 
				if mn not in ["login_count"]:
					continue
				#print("mid:", mid)
				measures = my_gnocchi_lib.get_measures(mid)
				nmeasures = len(measures)
				#print("%s len(measures):%d" %(mn, nmeasures))
				#print("%s measures:" %(mn), measures)
				if nmeasures < 2:
					continue
				begin = 0
				end = nmeasures-1

				# find logins in last 1 day
				d = measures[nmeasures-1][0] - measures[nmeasures -2][0]
				#if d != timedelta(1):
				#	continue
				#for i in range(end-1,-1,-1):
				#	print("end:", measures[end][0], " then:", measures[i][0])
				#print("diff: ", str(d), " :", d)
				login_count = measures[nmeasures-1][2]
				start_tm = measures[nmeasures-1][0]

				d = measures[nmeasures-1][0] - measures[nmeasures -2][0]
				if d != timedelta(1):
					continue

			# if login_count could not fetched last night, no need to check load_average, pwr 
			if not start_tm:
				continue

			# Check under utilization
			min_load_avg = -1  # Load Average in last 1 day
			for mn,mid in machines_hash[mach['hostname']]['resource']['metrics'].items(): 
				if mn not in ["load_avg"]:
					continue
				#print("mid:", mid)
				measures = my_gnocchi_lib.get_measures(mid)
				nmeasures = len(measures)
				#print("%s len(measures):%d" %(mn, nmeasures))
				#print("%s measures:" %(mn), measures)
				if nmeasures < 2:
					continue
				begin = 0
				end = nmeasures-1

				# find load_avg in last 1 day
				for i in range(end-1,-1,-1):
					#print("end:", measures[end][0], " then:", measures[i][0])
					if measures[i][0] >= start_tm:
						continue
					if start_tm - measures[i][0] >= timedelta(1):
						break
					if measures[i][2] < 0:
						continue
					if measures[i][2] == 0:
						min_load_avg = measures[i][2]
						continue
					if measures[i][2] > 0:
						min_load_avg = measures[i][2]
						break

			print("last 1 day measures of %s:: login_count:%d, load_avg:%f" %(mach['hostname'], login_count, min_load_avg))

			# Find utilization based on hueristic
			if login_count == -3 or min_load_avg == -3: # host powered off
				util_off_count += 1
			elif login_count == -2 or min_load_avg == -2: # host access errd
				util_error_count += 1
			elif login_count == -1 or min_load_avg == -1: # no host access
				#print("unknown login_count and load_avg")
				util_unknown_count += 1
			elif login_count > 0 or min_load_avg > 0.03:
				utilized = True
				util_nonzero_count += 1
			else:
				utilized = False
				util_zero_count += 1
				send_flag = True

			pwr_off_sum = 0
			pwr_off_count = 0
			pwr_unknown_sum = 0
			pwr_unknown_count = 0
			pwr_util_sum = 0
			pwr_util_count = 0
			pwr_unutil_sum = 0
			pwr_unutil_count = 0

			for mn,mid in machines_hash[mach['hostname']]['resource']['metrics'].items(): 
				if mn not in ["Pwr Consumption"]:
					continue
				#print("mid:", mid)
				measures = my_gnocchi_lib.get_measures(mid)
				nmeasures = len(measures)
				# find power consumed in last 1 day
				for i in range(end-1,-1,-1):
					if measures[i][0] >= start_tm:
						continue
					#print("end:", measures[end][0], " then:", measures[i][0], " val:", measures[i][2])
					if start_tm - measures[i][0] >= timedelta(1):
						break
					if measures[i][2] < 0:
						continue
					if measures[i][2] == 0:
						continue
					# implicitly measures[i][2] > 0:
					if utilized == None:
						pwr_unknown_sum += measures[i][2]
						pwr_unknown_count += 1
					elif utilized:
						pwr_util_sum += measures[i][2]
						pwr_util_count += 1
					else:
						pwr_unutil_sum += measures[i][2]
						pwr_unutil_count += 1

				#print("pwr_off_sum:", pwr_off_sum)
				#print("pwr_off_sum:", pwr_off_sum)
				#print("pwr_unknown_count:", pwr_unknown_count)
				#print("pwr_util_sum:", pwr_util_sum)
				#print("pwr_util_count:", pwr_util_count)
				#print("pwr_unutil_sum:", pwr_unutil_sum)
				#print("pwr_unutil_count:", pwr_unutil_count)

				if pwr_off_count > 0:
					pwr_off_avg += pwr_off_sum/pwr_off_count
				if pwr_unknown_count > 0:
					pwr_unknown_avg += pwr_unknown_sum/pwr_unknown_count
				if pwr_util_count > 0:
					pwr_util_avg += pwr_util_sum/pwr_util_count
				if pwr_unutil_count > 0:
					pwr_unutil_avg += pwr_unutil_sum/pwr_unutil_count

			if utilized == None or utilized:
				continue

			print("User: ", user, "'s hostname: ", mach['hostname'], " was under utilized.")

			if not args.noemail and not utilized:
				message += "<b>%s</b> :" %(mach['hostname'])
				message += "<a href='%s/MAAS/#/machine/%s\n'>Off</a> / " %(regctrl, mach['system_id'])
				message += "<a href='%s/MAAS/#/machine/%s\n'>Release</a> / " %(regctrl, mach['system_id'])
				message += "<a href='%s/MAAS/#/machine/%s\n'>On</a>" %(regctrl, mach['system_id'])
				message += "<br>"

		if not args.noemail and send_flag:
			message += "<br><br>Please release them or power them off to save energy.<br>"
			message += "You can acquire them again or power them on whenever needed.<br>"
			message += "<br>--BMaaS Admin.<br>"

			print("Sending email to user: ", user, " emailid:", users[user]["email"])
			msg.set_payload(message)
			# sending the mail
			s.sendmail(msg['From'], [msg['To']], msg.as_string())

	print("util_off_count:", util_off_count)
	print("util_nonzero_count:", util_nonzero_count)
	print("util_zero_count:", util_zero_count)
	print("util_unknown_count:", util_unknown_count)
	print("util_error_count:", util_error_count)
	print("pwr_off_avg:", pwr_off_avg)
	print("pwr_unutil_avg:", pwr_unutil_avg)
	print("pwr_util_avg:", pwr_util_avg)
	print("pwr_unknown_avg:", pwr_util_avg)

	if start_tm:
		resource_measures = []
		utc_dt = start_tm
		aware_utc_dt = utc_dt.replace(tzinfo=pytz.utc)
		tm = aware_utc_dt.strftime('%Y-%m-%d %H:%M:%S')
		# add machine_count and power_consump_sum as resource
		resource_measures.append({
			'resource_key' : "total_machines",  # using machine header for the sake of generality
			'measures' : [
				{ 'time': tm, 'type' : 'util_off_count', 'value' : util_off_count },
				{ 'time': tm, 'type' : 'util_error_count', 'value' : util_error_count },
				{ 'time': tm, 'type' : 'util_unknown_count', 'value' : util_unknown_count },
				{ 'time': tm, 'type' : 'util_zero_count', 'value' : util_zero_count },
				{ 'time': tm, 'type' : 'util_nonzero_count', 'value' : util_nonzero_count }
			]
		})
		resource_measures.append({
			'resource_key' : "total_machines",  # using machine header for the sake of generality
			'measures' : [
				{ 'time': tm, 'type' : 'pwr_off_avg', 'value' : pwr_off_avg },
				{ 'time': tm, 'type' : 'pwr_util_avg', 'value' : pwr_util_avg },
				{ 'time': tm, 'type' : 'pwr_unutil_avg', 'value' : pwr_unutil_avg },
				{ 'time': tm, 'type' : 'pwr_unknown_avg', 'value' : pwr_unknown_avg }
			]
		})
		if not args.nostore :
			my_gnocchi_lib.save_in_gnocchi("fetchd", resource_measures)
	# terminating the session
	s.quit()


if __name__ == "__main__":
	# Parse the command line arguments
	parser = argparse.ArgumentParser(description='script to detect utilization of machines based on inband data')
	parser.add_argument('--noemail', default=False, action='store_true', help='noemail')
	parser.add_argument('--nostore', default=False, action='store_true', help='nostore')

	args = parser.parse_args()
	#print(args)

	# Plant a signal handler for Ctrl+C
	signal.signal(signal.SIGINT, sigint_handler)

	# Create separate process for checking under utilization
	# threads dont work, as asyncio has per-process global data structures.
	duu_job = multiprocessing.Process(target = detect_under_utilization, args = (0,), daemon=True)

	# start the child processes
	duu_job.start()

	# wait for the children to join back
	duu_job.join()

	sys.exit(0)

