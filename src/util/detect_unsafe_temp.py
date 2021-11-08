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
import json

def sigint_handler(signum, frame):
    print('INT Signal handler called with signal', signum)
    sys.exit(0)

regctrl = my_maas_lib.regctrl_url

def detect_unsafe_temp(interval):
    user_list = my_maas_lib.get_users()
    users = {}
    for user in user_list:
        users[user['username']] = user
    ret = my_maas_lib.get_machines()
    machines_list = json.loads(ret)
    machines_hash = dict()
    users_machines_hash = dict()
    for mach in machines_list:
        if mach['power_state'] != 'on':
            continue

        if mach['owner'] not in users_machines_hash:
            users_machines_hash[mach['owner']] = []
        m = {
                'hostname' : mach['hostname'],
                'system_id' : mach['system_id'],
                'hardware_info' : mach['hardware_info'],
                'owner' : mach['owner'],
                'resource_uri' : mach['resource_uri'],
                'resource' : ""
            }
        machines_hash[mach['hostname']] = m
        users_machines_hash[mach['owner']].append(m)

    resources = my_gnocchi_lib.get_resources()
    for r in resources:
        hostname = r['original_resource_id'].split(':')[1]
        if hostname in machines_hash:
            machines_hash[hostname]['resource'] = r

    with open("/etc/dhi-ojas/system_prod_temp.json", 'r') as data:
        safe_temp_data = json.load(data)
    

    with open("/etc/dhi-ojas/email.yml", 'r') as stream:
        email_config = yaml.safe_load(stream)['email']

    s = smtplib.SMTP(email_config['smtpserver'], email_config['port'])
    s.ehlo()
    s.starttls()
    s.login(email_config['emailid'], email_config['appkey'])
    for user, mlist in users_machines_hash.items():
        if user is None:
            continue
        send_flag = False
        msg = email.message.Message()
        msg['Subject'] = 'Unsafe operating temperature alert'
        msg['From'] = email_config['emailid']
        #msg['To'] = users[user]["email"]
        msg['To'] = 'cs19mtech11027@iith.ac.in'
        msg.add_header('Content-Type','text/html')
        message = "\nDear %s,<br><br>" %(user)
        message += "The following machines are not in safe operating temperature range.<br><br>"
        
        for mach in mlist:
            inlet_flag = False
            exhaust_flag = False

            for mn,mid in machines_hash[mach['hostname']]['resource']['metrics'].items():
                if mn not in ["Inlet Temp", "Exhaust Temp"]:
                    continue
                #print("mid:", mid)
                #print("measure:", my_gnocchi_lib.get_measures(mid)[-1])
                if mn == "Inlet Temp":
                    inlet_temp = my_gnocchi_lib.get_measures(mid)[-1][2]
                    if inlet_temp > 21:
                        inlet_flag = True
                else:
                    exhaust_temp = my_gnocchi_lib.get_measures(mid)[-1][2]
                    if exhaust_temp > safe_temp_data[mach['hardware_info']['system_product']]['max']:
                        exhaust_flag = True
                        
            print("last 1 day measures of %s:: inlet_temp:%d, exhaust_temp:%f" %(mach['hostname'], inlet_temp, exhaust_temp))
            if inlet_flag or exhaust_flag:
                message += "<b>%s</b> :" %(mach['hostname'])
                message += "<a href=%s/MAAS/#/machine/%s\n>Off</a> / " %(regctrl, mach['system_id'])
                message += "<a href=%s/MAAS/#/machine/%s\n>Release</a> / " %(regctrl, mach['system_id'])
                message += "<a href=%s/MAAS/#/machine/%s\n>On</a> / " %(regctrl, mach['system_id'])
                message += "<br>"
                send_flag = True

        if send_flag:
            message += "<br><br>Please release them or power them off to avoid risk of failure.<br>"
            message += "<br>--BMaas Admin.<br>"
            print("sending email to user: ", user, "emailid: ", users[user]["email"])
            msg.set_payload(message)
            s.sendmail(msg['From'], msg['To'], msg.as_string())

    s.quit()


if __name__ == "__main__":
    signal.signal(signal.SIGINT, sigint_handler)
    duu_job = multiprocessing.Process(target = detect_unsafe_temp, args = (0,), daemon=True)
    duu_job.start()
    duu_job.join()
    sys.exit(0)
