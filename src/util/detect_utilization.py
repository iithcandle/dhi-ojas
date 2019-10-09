#!/usr/bin/env python3

#
# Copyright (C) 2018-2019 Maruthi Seshidhar Inukonda - All Rights Reserved.
# maruthi.inukonda@gmail.com
#
# This file is released under the Affero GPLv3 License.
#
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
	machines_list = my_maas_lib.get_machines(True, False)
	hosts =[]
	machines_hash = dict()
	users_machines_hash = dict()
	for mach in machines_list:
		# Only deployed machines could have agent running.
		#if mach['status_name'] != "Deployed":
		#	continue
		# Only powered on systems' agent is reachable.
		if mach['power_state'] != 'on':
			continue
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
		msg['To'] = users[user]["email"]
		msg.add_header('Content-Type','text/html')
		message = "\nDear %s,<br><br>" %(user)
		message += "The following machines are under utilized.<br><br>"
		for mach in mlist:
			print("machine:", mach['hostname'])
			# Check under utilization
			login_count = 0 # Login count in last 1 day
			min_load_avg = 0.0  # Load Average in last 1 day
			for mn,mid in machines_hash[mach['hostname']]['resource']['metrics'].items(): 
				if mn not in ["login_count", "load_avg"]:
					continue
				print("mid:", mid)
				measures = my_gnocchi_lib.get_measures(mid)
				nmeasures = len(measures)
				print("%s len(measures):%d" %(mn, nmeasures))
				#print("%s measures:" %(mn), measures)
				if nmeasures < 2:
					continue
				begin = 0
				end = nmeasures-1
				if mn == "login_count":
					# find logins in last 1 day
					d = measures[nmeasures-1][0] - measures[nmeasures -2][0]
					#if d != timedelta(1):
					#	continue
					#for i in range(end-1,-1,-1):
					#	print("end:", measures[end][0], " then:", measures[i][0])
					#print("diff: ", str(d), " :", d)
					login_count = measures[nmeasures-1][2]
				elif mn == "load_avg":
					# find load_avg in last 1 day
					min_load_avg = 0
					for i in range(end-1,-1,-1):
						#print("end:", measures[end][0], " then:", measures[i][0])
						if measures[end][0] - measures[i][0] >= timedelta(1):
							break
						if measures[i][2] != 0:
							min_load_avg = measures[i][2]
							break
					d = measures[nmeasures-1][0] - measures[nmeasures -2][0]
					if d != timedelta(1):
						continue
					min_load_avg = measures[nmeasures-1][2]
			print("last 1 day measures of %s:: login_count:%d, load_avg:%f" %(mach['hostname'], login_count, min_load_avg))
			if login_count > 0 or min_load_avg > 0.03:
				continue
			message += "<b>%s</b> :" %(mach['hostname'])
			message += "<a href='%s/MAAS/#/machine/%s\n'>Off</a> / " %(regctrl, mach['system_id'])
			message += "<a href='%s/MAAS/#/machine/%s\n'>Release</a> / " %(regctrl, mach['system_id'])
			message += "<a href='%s/MAAS/#/machine/%s\n'>On</a>" %(regctrl, mach['system_id'])

			send_flag = True

		if send_flag:
			message += "<br><br>Please release them or power them off to save energy.<br>"
			message += "You can acquire them again or power them on whenever needed.<br>"
			message += "<br>--BMaaS Admin.<br>"

			print("Sending email to user: ", user, " emailid:", users[user]["email"])
			msg.set_payload(message)
			# sending the mail
			s.sendmail(msg['From'], [msg['To']], msg.as_string())

	# terminating the session
	s.quit()


if __name__ == "__main__":
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

