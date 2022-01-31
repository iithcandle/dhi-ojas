#!/usr/bin/env python3

#
# Copyright (C) 2018-2022 Maruthi Seshidhar Inukonda - All Rights Reserved.
# maruthi.inukonda@gmail.com
#
# This file is released under the Affero GPLv3 License.
#

import json
import requests
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

def get_resourcepool():
        # Establish a session
        s = Session()

        # Send GET machines request
        url = u'%s/MAAS/api/2.0/resourcepools/' %(regctrl_url)
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

def get_scripts():
	# Establish a session
	s = Session()

	# Only successfully commissioned machines have machine details available.
	# Send GET scripts
	url = u'%s/MAAS/api/2.0/scripts/' %(regctrl_url)
	headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
	req = Request('GET', url, data=None, headers=headers, auth=auth1)
	prepped = req.prepare()
	resp = s.send(prepped)
	print('resp.headers:', resp.headers)
	#print("dir(resp):", dir(resp), "\n")
	#print("details resp.text:", resp.text, "\n")
	#print("resp.text.isprintable():", resp.text.isprintable())
	return resp.text

def get_nodes():
	# Establish a session
	s = Session()

	# Send GET nodes
	url = u'%s/MAAS/api/2.0/nodes/' %(regctrl_url)
	headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
	req = Request('GET', url, data=None, headers=headers, auth=auth1)
	prepped = req.prepare()
	resp = s.send(prepped)
	print('resp.headers:', resp.headers)
	#print("dir(resp):", dir(resp), "\n")
	#print("details resp.text:", resp.text, "\n")
	#print("resp.text.isprintable():", resp.text.isprintable())
	return resp.text

def post_machines_test(system_id, test_name):
	# Establish a session
	s = Session()

	# Only successfully commissioned machines have machine details available.
	# Send GET machine details request
	#url = u'%s/MAAS/api/2.0/machines/%s/?op=test&testing_scripts=%s' %(regctrl_url, system_id, test_name)
	url = u'%s/MAAS/api/2.0/machines/%s/?op=test' %(regctrl_url, system_id)
	param = {'testing_scripts': test_name}
	headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
	#resp = requests.post(url, auth=auth1, json=param)
	req = Request('POST', url, data=None, json=param, headers=headers, auth=auth1)
	prepped = req.prepare()
	resp = s.send(prepped)
	#print('resp.headers:', resp.headers)
	#print("dir(resp):", dir(resp), "\n")
	#print(resp)
	#print("details resp.text:", resp.text, "\n")
	#print("resp.text.isprintable():", resp.text.isprintable())

def get_nodes_results(system_id, test_id):
	# Establish a session
	s = Session()

	# Only successfully commissioned machines have machine details available.
	# Send GET machine details request
	#url = u'%s/MAAS/api/2.0/nodes/%s/results/%s/' %(regctrl_url, system_id, test_id)
	url = u'%s/MAAS/api/2.0/nodes/%s/results/current-testing/' %(regctrl_url, system_id)
	headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
	req = Request('GET', url, data=None, headers=headers, auth=auth1)
	prepped = req.prepare()
	resp = s.send(prepped)
	print('resp.headers:', resp.headers)
	#print("dir(resp):", dir(resp), "\n")
	#print("details resp.text:", resp.text, "\n")
	#print("resp.text.isprintable():", resp.text.isprintable())
	return resp
	#return resp.text

def get_power_status(system_id):
	#GET /MAAS/api/2.0/machines/{system_id}/?op=query_power_state

	# Establish a session
	s = Session()

	# Works only when machine is not in locked state.
	# In locked state, even in GUI, configuration tab (which shows these power parameters) vanishes.
	# Send GET power_parameters
	url = u'%s/MAAS/api/2.0/machines/%s/?op=query_power_state' %(regctrl_url, system_id)
	headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
	req = Request('GET', url, data=None, headers=headers, auth=auth1)
	prepped = req.prepare()
	resp = s.send(prepped)
	#print('resp.headers:', resp.headers)
	#print('type(resp.text):', type(resp.text))
	#print('resp.text:', resp.text)
	return resp.text

def post_power_off(system_id):
	#POST /MAAS/api/2.0/machines/{system_id}/?op=power_off

	# Establish a session
	s = Session()

	# Works only when machine is not in locked state.
	# In locked state, even in GUI, configuration tab (which shows these power parameters) vanishes.
	# Send GET power_parameters
	url = u'%s/MAAS/api/2.0/machines/%s/?op=power_off' %(regctrl_url, system_id)
	headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
	param = {'stop_mode': 'soft'}
	req = Request('POST', url, data=None, json=param, headers=headers, auth=auth1)
	prepped = req.prepare()
	resp = s.send(prepped)
	#print('resp.headers:', resp.headers)
	#print('type(resp.text):', type(resp.text))
	#print('resp.text:', resp.text)
	return resp.text

def post_power_on(system_id):
	#POST /MAAS/api/2.0/machines/{system_id}/?op=power_on

	# Establish a session
	s = Session()

	# Works only when machine is not in locked state.
	# In locked state, even in GUI, configuration tab (which shows these power parameters) vanishes.
	# Send GET power_parameters
	url = u'%s/MAAS/api/2.0/machines/%s/?op=power_on' %(regctrl_url, system_id)
	headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
	param = {'comment': 'powered on from doshell'}
	req = Request('POST', url, data=None, json=param, headers=headers, auth=auth1)
	prepped = req.prepare()
	resp = s.send(prepped)
	#print('resp.headers:', resp.headers)
	#print('type(resp.text):', type(resp.text))
	#print('resp.text:', resp.text)
	return resp.text


def post_deploy(system_id):
	#POST /MAAS/api/2.0/machines/{system_id}/?op=deploy

	# Establish a session
	s = Session()

	# Works only when machine is not in locked state.
	# In locked state, even in GUI, configuration tab (which shows these power parameters) vanishes.
	# Send GET power_parameters
	url = u'%s/MAAS/api/2.0/machines/%s/?op=deploy' %(regctrl_url, system_id)
	param = {'comment': 'dedploy the machine'}
	headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
	#resp = requests.post(url, auth=auth1, json=param)
	req = Request('POST', url, data=None, json=param, headers=headers, auth=auth1)
	prepped = req.prepare()
	resp = s.send(prepped)
	#print('resp.headers:', resp.headers)
	#print('type(resp.text):', type(resp.text))
	#print('resp.text:', resp.text)
	return resp.text


def post_release(system_id):
	#POST /MAAS/api/2.0/machines/{system_id}/?op=release

	# Establish a session
	s = Session()

	# Works only when machine is not in locked state.
	# In locked state, even in GUI, configuration tab (which shows these power parameters) vanishes.
	# Send GET power_parameters
	url = u'%s/MAAS/api/2.0/machines/%s/?op=release' %(regctrl_url, system_id)
	headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
	param = {'comment':'release a machine'}
	headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
	#resp = requests.post(url, auth=auth1, json=param)
	req = Request('POST', url, data=None, json=param, headers=headers, auth=auth1)
	prepped = req.prepare()
	resp = s.send(prepped)
	#print('resp.headers:', resp.headers)
	#print('type(resp.text):', type(resp.text))
	#print('resp.text:', resp.text)
	return resp.text

def post_commision(system_id):
	#POST /MAAS/api/2.0/machines/{system_id}/?op=commission

	# Establish a session
	s = Session()

	# Works only when machine is not in locked state.
	# In locked state, even in GUI, configuration tab (which shows these power parameters) vanishes.
	# Send GET power_parameters
	url = u'%s/MAAS/api/2.0/machines/%s/?op=commission' %(regctrl_url, system_id)
	param = {}
	headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
	#resp = requests.post(url, auth=auth1, json=param)
	req = Request('POST', url, data=None, json=param, headers=headers, auth=auth1)
	prepped = req.prepare()

	resp = s.send(prepped)
	#print('resp.headers:', resp.headers)
	#print('type(resp.text):', type(resp.text))
	#print('resp.text:', resp.text)
	return resp.text



def post_allocate(system_id):
        #POST /MAAS/api/2.0/machines/?op=allocate

        # Establish a session
        s = Session()

        # Works only when machine is not in locked state.
        # In locked state, even in GUI, configuration tab (which shows these power parameters) vanishes.
        # Send GET power_parameters
        url = u'%s/MAAS/api/2.0/machines/?op=allocate' %(regctrl_url)
        headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
        param = {'system_id' : system_id }
        headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
        #resp = requests.post(url, auth=auth1, json=param)
        req = Request('POST', url, data=None, json=param, headers=headers, auth=auth1)
        prepped = req.prepare()
        resp = s.send(prepped)
        #print('resp.headers:', resp.headers)
        #print('type(resp.text):', type(resp.text))
        #print('resp.text:', resp.text)
        
        return resp.text

