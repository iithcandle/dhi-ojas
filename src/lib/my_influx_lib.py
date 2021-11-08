#!/usr/bin/env python3

import yaml
import io
import influxdb

with open("/etc/dhi-ojas/influx.yml", 'r') as stream:
    influx_config = yaml.safe_load(stream)


influx_url = influx_config['influx']['endpoint_url']
influx_username = influx_config['influx']['username']
influx_password = influx_config['influx']['password']

client = influxdb.InfluxDBClient(host=influx_url,port=8086, username=influx_username, password=influx_password)
if not client:
    print("Error connecting to InfluxDB ")
    sys.exit(2)


def save_in_influx(dbase, resources_list):
    try:
        client = influxdb.InfluxDBClient(host=influx_url,port=8086,database=dbase, username=influx_username, password=influx_password)
        try:
            client.write_points(points=resources_list, retention_policy='autogen') 
        except Exception as e:
            print("Error occured while inserting into InfluxDB: ", e)
    except:
        print("Error connecting to InfluxDB ")
