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
$ sudo vi /etc/dhi-ojas/influx.yml
$ sudo vi /etc/dhi-ojas/machines_nonmaas.yml
$ sudo vi /etc/dhi-ojas/machines_skip.yml
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

## Citation
```
@techreport { ref113,
	title            = "A Solution Architecture of Bare-metal As A Service Cloud using Open-source Tools",
	year             = "2019",
	author           = "Maruthi S Inukonda and Sparsh Mittal and Sai Harsh Kottapalli",
	institution      = "IIT Hyderabad",
	number           = "2019-CSE-CANDLE-02",
	doi              = "10.13140/RG.2.2.25057.45927",
	url              = "https://www.researchgate.net/publication/336319828_A_Solution_Architecture_of_Bare-metal_As_A_Service_Cloud_using_Open-source_Tools",
	abstract         = "Research and development labs in academia and industry use bare-metal servers to do benchmarking of software
						systems. In the last decade, cloud computing has grown drastically and it has replaced private data centers
						for many organizations. But bare-metal as a service type of clouds have not become popular due to the
						lower effectiveness of power utilization in these servers and manual intensive work in re-purposing machines.
						In this paper we propose a solution architecture that addresses these issues. The solution architecture is
						implemented in a small-scale data-center in an educational institute. Our solution uses only open source and
						open infrastructure and thus,  avoids vendor lock-in. Our work removes the requirement of manual work using
						MAAS open source software. The monitoring and alerting services of our solution help the data-center
						administrators and computing-system owners in improving the power utilization efficiency, which also leads
						to monetary savings. The code developed is available as open-source at https://github.com/iithcandle/dhi-ojas"}
```

## Disclaimer

The code published is work-in-progress, and shared under AGPLv3 (no warranty, no guarantee).
Any issues reported will be fixed on best-effort basis.
