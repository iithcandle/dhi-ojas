#!/usr/bin/env python3

#
# Copyright (C) 2018-2022 Maruthi Seshidhar Inukonda - All Rights Reserved.
# maruthi.inukonda@gmail.com
#
# This file is released under the Affero GPLv3 License.
#

import collections
from gnocchiclient import auth, exceptions
from gnocchiclient.v1 import client, metric
import yaml
import io

# Read YAML file
with open("/etc/dhi-ojas/gnocchi.yml", 'r') as stream:
    gnocchi_config = yaml.safe_load(stream)

gnocchi_url = gnocchi_config['gnocchi']['endpoint_url']
gnocchi_username = gnocchi_config['gnocchi']['username']

# connect to gnocchi
try:
	auth_plugin = auth.GnocchiBasicPlugin(user=gnocchi_username, endpoint=gnocchi_url)
	gnocchi = client.Client(session_options={'auth': auth_plugin})
except:
	print("Error occured while autheticating gnocchi credentials!")
	sys.exit(2)

def get_resources():
	resources = gnocchi.resource.list()
	return resources

def get_measures(id):
	measures = gnocchi.metric.get_measures(id)
	return measures

def save_in_gnocchi(resource_type, resource_measures_list):
	# connect to gnocchi
	try:
		auth_plugin = auth.GnocchiBasicPlugin(user=gnocchi_username, endpoint=gnocchi_url)
		gnocchi = client.Client(session_options={'auth': auth_plugin})
	except:
		print("Error occured while autheticating gnocchi credentials!")
		sys.exit()

	# send data
	for r_m in resource_measures_list:
		# print(r_m)
		resource_name = resource_type + ":" + r_m["resource_key"]
		measures = { resource_name: collections.defaultdict(list) }
		for measure in r_m["measures"]:
			measures[resource_name][measure["type"]].append({
				"timestamp": measure["time"],
				"value": measure["value"],
			})

			try:
				try: # sending measures
					gnocchi.metric.batch_resources_metrics_measures(
								measures, create_metrics=True)
				except exceptions.BadRequest:
					# Create required resource and send again
					attrs = {"id": resource_name, "host": r_m["resource_key"]}
					try:
						try:
							gnocchi.resource.create(resource_type, attrs)
						except exceptions.ResourceTypeNotFound:
							try: # create resource type
								gnocchi.resource_type.create({
									"name": resource_type,
									"attributes": {
										"host": { "required": True, "type": "string", },
									}
								})
							except exceptions.ResourceTypeAlreadyExists:
								pass
							gnocchi.resource.create(resource_type, attrs)
					except exceptions.ResourceAlreadyExists:
						pass
					gnocchi.metric.batch_resources_metrics_measures(
							measures, create_metrics=True)
			except Exception as e:
				print("Unexpected Error!", e)
				try:
					auth_plugin = auth.GnocchiBasicPlugin(user=gnocchi_username, endpoint=gnocchi_url)
					gnocchi = client.Client(session_options={'auth': auth_plugin})
				except:
					print("Error occured while autheticating gnocchi credentials!")
					sys.exit()
				continue

def read_from_gnocchi(resource_type, resource_id):
	# connect to gnocchi
	try:
		auth_plugin = auth.GnocchiBasicPlugin(user=gnocchi_username, endpoint=gnocchi_url)
		gnocchi = client.Client(session_options={'auth': auth_plugin})
	except:
		print("Error occured while autheticating gnocchi credentials!")
		sys.exit()

	# retrieve data
	for r_m in resource_metrics_list:
		cmd = ""
		print(resource_type, r_m)
		'''
		resource_name = resource_type + ":" + r_m["resource_key"]
		measures = { resource_name: collections.defaultdict(list) }
		for measure in r_m["measures"]:
			measures[resource_name][measure["type"]].append({
				"timestamp": measure["time"],
				"value": measure["value"],
			})

			try:
				try: # sending measures
					gnocchi.metric.batch_resources_metrics_measures(
								measures, create_metrics=True)
				except exceptions.BadRequest:
					# Create required resource and send again
					attrs = {"id": resource_name, "host": r_m["resource_key"]}
					try:
						try:
							gnocchi.resource.create(resource_type, attrs)
						except exceptions.ResourceTypeNotFound:
							try: # create resource type
								gnocchi.resource_type.create({
									"name": resource_type,
									"attributes": {
										"host": { "required": True, "type": "string", },
									}
								})
							except exceptions.ResourceTypeAlreadyExists:
								pass
							gnocchi.resource.create(resource_type, attrs)
					except exceptions.ResourceAlreadyExists:
						pass
					gnocchi.metric.batch_resources_metrics_measures(
							measures, create_metrics=True)
			except Exception as e:
				print("Unexpected Error!", e)
				try:
					auth_plugin = auth.GnocchiBasicPlugin(user=gnocchi_username, endpoint=gnocchi_url)
					gnocchi = client.Client(session_options={'auth': auth_plugin})
				except:
					print("Error occured while autheticating gnocchi credentials!")
					sys.exit()
				continue
		'''


