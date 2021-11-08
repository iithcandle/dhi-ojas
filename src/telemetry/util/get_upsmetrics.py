#!/usr/bin/env python3
from pysnmp.hlapi import *
import io
import yaml
import my_influx_lib
import time
from datetime import datetime, timedelta
import pytz

with open("../../config/upsconfig.yml", 'r') as stream:
    config = yaml.safe_load(stream)

oids = config['oidmap']

for ups in config['ups']:
    ups_ip = config['ups'][ups]['ip']
    auth = config['ups'][ups]['auth']
    priv = config['ups'][ups]['priv']
    username = config['ups'][ups]['username']
    password = config['ups'][ups]['password']
    upsoids = config['ups'][ups]['oids']
    #print(upsoids)
    #upsoidobjs = [ObjectType(ObjectIdentity( x )) for x in upsoids]
    values = []

    for x in upsoids:   
        iterator = getCmd(
            SnmpEngine(),
            UsmUserData(username, password, password),
            UdpTransportTarget((ups_ip, 161)),
            ContextData(),
            ObjectType(ObjectIdentity( x ))
            #*upsoidobjs,
        )

        errorIndication, errorStatus, errorIndex, varBinds = next(iterator)
        
        if errorIndication:
            print(errorIndication)
        elif errorStatus:
            print('%s at %s' % (errorStatus.prettyPrint(),
                        errorIndex and varBinds[int(errorIndex) - 1][0] or '?'))
        else:
        #for varBind in varBinds:
        #   print("Hi")
        #   print(' = '.join([x.prettyPrint() for x in varBind]))
        #   for x in varBind:
        #       print(x.prettyPrint())
            ts = time.time()
            utc_dt = datetime.utcfromtimestamp(ts)
            aware_utc_dt = utc_dt.replace(tzinfo=pytz.utc)
            tm = aware_utc_dt.strftime('%Y-%m-%d %H:%M:%S')

            for varBind in varBinds:
                values.append({
                    "measurement": oids[str(varBind[0].prettyPrint())]['type'],
                    "time":tm,
                    "tags":{
                        "ups": ups,
                        "io":   oids[str(varBind[0].prettyPrint())]['io'],
                        "phase":oids[str(varBind[0].prettyPrint())]['phase']
                        },
                    "fields":{
                        "value":float(varBind[1].prettyPrint())/10 if 
                            oids[str(varBind[0].prettyPrint())]['type'] == 'current' else float(varBind[1].prettyPrint())
                        }
                })
    print(values)
    my_influx_lib.save_in_influx('ups',values)
   
