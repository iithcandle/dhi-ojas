# dhi-ojas
Intelligent energy saving applications and services from BMaaS solution developed at CSE department, IIT Hyderabad, India


# Installation

On region controller, follow the below installation steps

```
$ git clone https://github.com/iithcandle/dhi-ojas
$ cd dhi-ojas
$ sudo mkdir -p /etc/dhi-ojas/ /usr/local/lib/python3.6/dist-packages/dhi-ojas/
$ sudo cp src/config/* /etc/dhi-ojas/
$ sudo cp src/lib/*.py /usr/local/lib/python3.6/dist-packages/dhi-ojas/
$ sudo cp src/util/fetch_proxy.py /usr/local/bin/fetch_proxy
$ sudo cp src/util/detect_utilization.py /usr/local/bin/detect_utilization
$ sudo chmod u+w /usr/local/bin/fetch_proxy /usr/local/bin/detect_utilization
```

On each of the rack controllers, follow the below installation steps

```
$ git clone https://github.com/iithcandle/dhi-ojas
$ cd dhi-ojas
$ sudo mkdir -p /etc/dhi-ojas/ /usr/local/lib/python3.6/dist-packages/dhi-ojas/
$ sudo cp src/config/* /etc/dhi-ojas/
$ sudo cp src/lib/*.py /usr/local/lib/python3.6/dist-packages/dhi-ojas/
$ sudo cp src/util/fetch_proxy.py /usr/local/bin/fetch_proxy
$ sudo chmod u+w /usr/local/bin/fetch_proxy
```


# Configuration

On the region controller and all the rack controllers, follow the below configuration steps
```
$ sudo vi /etc/dhi-ojas/email.yml
$ sudo vi /etc/dhi-ojas/maas.yml
$ sudo vi /etc/dhi-ojas/gnocchi.yml
$ sudo vi /etc/dhi-ojas/hosts.yml
```

# Testing #

## From command line ##

On all the rack controllers, follow the below test steps

### Out-of-band proxy ###

```
$ python3 /usr/local/bin/fetch_proxy --bmc_data --machine_state New Deployed
```

### In-band proxy ###

```
$ python3 /usr/local/bin/fetch_proxy --load_avg --login_count --machine_state Deployed
```

On the region controller, follow the below test steps

### Under-utillzation detection and Alerting engine ###
```
$ python3 /usr/local/bin/detect_utilization
``` 

## From Jenkins ##

Once tests pass, run the scripts from Jenkins jobs at scheduled interval.

- In our setup, the in-band proxy (with --load_avg) and the out-of-band proxy (with --bmc_data) is run every 5 minutes.
- The in-band proxy (with --login_count) is again run every night 00:00.
- The detection and alert agent is run every morning at 06:00.



