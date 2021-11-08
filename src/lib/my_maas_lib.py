#!/usr/bin/env python3

#
# Copyright (C) 2018-2020 Maruthi Seshidhar Inukonda - All Rights Reserved.
# maruthi.inukonda@gmail.com
#
# This file is released under the Affero GPLv3 License.
#

import json
from requests import Request, Session
from requests_oauthlib import OAuth1
import sys
import yaml
import io
#import xml.etree.ElementTree as ET
import xmltodict

# Reference: https://maas.io/docs/api

# Read YAML file
with open("/etc/dhi-ojas/maas.yml", 'r') as stream:
    maas_config = yaml.safe_load(stream)

regctrl_url = maas_config['maas']['regctrl_endpoint_url']
consumer_key = maas_config['maas']['oauth']['consumer_key']
token_key = maas_config['maas']['oauth']['token_key']
token_secret = maas_config['maas']['oauth']['token_secret']
auth1 = OAuth1(consumer_key, '', token_key, token_secret)

def get_users():
	# Establish a session
	s = Session()

	# Send GET users request
	url = u'%s/MAAS/api/2.0/users/' %(regctrl_url)
	headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
	req = Request('GET', url, data=None, headers=headers, auth=auth1)
	prepped = req.prepare()
	resp = s.send(prepped)
	#print('resp.headers:', resp.headers)
	#print('type(resp.text):', type(resp.text))
	#print('resp.text:', resp.text)
	user_list = json.loads(resp.text)

	return user_list

def get_machines():
	# Establish a session
	s = Session()

	# Send GET machines request
	url = u'%s/MAAS/api/2.0/machines/' %(regctrl_url)
	headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
	req = Request('GET', url, data=None, headers=headers, auth=auth1)
	prepped = req.prepare()
	resp = s.send(prepped)
	#print('resp.headers:', resp.headers)
	#print('type(resp.text):', type(resp.text))
	##print('resp.text:', resp.text)
	return resp.text

def get_machine_power_parameters(system_id):
	# Establish a session
	s = Session()

	# Works only when machine is not in locked state.
	# In locked state, even in GUI, configuration tab (which shows these power parameters) vanishes.
	# Send GET power_parameters
	url = u'%s/MAAS/api/2.0/machines/%s/?op=power_parameters' %(regctrl_url, system_id)
	headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
	req = Request('GET', url, data=None, headers=headers, auth=auth1)
	prepped = req.prepare()
	resp = s.send(prepped)
	#print('resp.headers:', resp.headers)
	#print('type(resp.text):', type(resp.text))
	#print('resp.text:', resp.text)
	return resp.text

def get_machine_details(system_id):
	# Establish a session
	s = Session()

	# Only successfully commissioned machines have machine details available.
	# Send GET machine details request
	url = u'%s/MAAS/api/2.0/machines/%s/?op=details' %(regctrl_url, system_id)
	headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
	req = Request('GET', url, data=None, headers=headers, auth=auth1)
	prepped = req.prepare()
	resp = s.send(prepped)
	#print('resp.headers:', resp.headers)
	#print("dir(resp):", dir(resp), "\n")
	#print("details resp.text:", resp.text, "\n")
	#print("resp.text.isprintable():", resp.text.isprintable())
	return resp.text

