For old nascent design (with jenkins based, periodically genrated dataset)
=========================================================================
$ python3 fetch_proxy.py --nostore --bmc_data --dump --dumpdir logs/20200303/
$ python3 collect_train_data.py --timeseries --download --inventory
$ python3 collect_train_data.py --inventory --curate --timeseries --dirraw data/20200303_113006/raw/ --dircurated data/20200303_113006/curated
(base)$ python3 encode_train_data.py --encode --dircurated /var/lib/dhi-ojas/data/cum_curated --direncoded /var/lib/dhi-ojas/data/data/cum_encoded_bm_wtemp --encoding_inlet_temp as-is
(base)$ python3 encode_train_data.py --encode --dircurated /var/lib/dhi-ojas/data/cum_curated --direncoded /var/lib/dhi-ojas/data/data/cum_encoded_bm_wtemp --encoding_inlet_temp as-is --include_timestamp
(base)$ python3 generate_model.py  --direncoded /var/lib/dhi-ojas/data/cum_encoded_bm_wtemp --dirmodel data/cum_model_binary --selection random --ctype binary
(base)$ python3 generate_model.py  --direncoded /var/lib/dhi-ojas/data/cum_encoded_bm_wtemp --dirmodel data/cum_model_multi --selection random --ctype multi

For new nascent design (with hwtesting based, benchmark genrated dataset)
=========================================================================
python3 a_download_inventory.py  --dirraw data/latest/a_raw_inventory/
python3 b_curate_inventory.py --dirraw data/latest/a_raw_inventory/
python3 c_encode_inventory.py --dircurated data/latest/b_curated_inventory/
python3 d_find_machine_subset.py --direncoded data/latest/c_encoded_inventory/

Data collection (Regression & Classifcation):
--------------------------------------------
time python3 e_run_benchmarks.py --dirrawdata data/latest/e_raw_benchmark --workload nascent_quick_test
time python3 e_collect_realdata.py --dirrawdata data/latest/e_raw_production

Curation (Regression & Classifcation):
-------------------------------------
time python3 f_curate_benchmark.py --dirrawdata data/latest/e_raw_benchmark/  --dircurateddata data/latest/f_curated_benchmark/ --drift 5 --wtype benchmark --workload nascent_cpu_benchmark --workload nascent_idle_benchmark
time python3 f_curate_benchmark.py --dirrawdata data/latest/e_raw_production/ --dircurateddata data/latest/f_curated_production/ --drift 5 --wtype production --workload real 

Encoding (Classification):
-------------------------
time python3 g_encode_benchmark.py --dircurateddata data/latest/f_curated_benchmark/  --wtype benchmark --cpuload_threshold 0.01 --encoding_cpuload class
time python3 g_encode_benchmark.py --dircurateddata data/latest/f_curated_production/ --wtype production --cpuload_threshold 0.01 --encoding_cpuload class

Training (Classification):
-------------------------
time python3 h_generate_model.py  --direncodedtraindata data/latest/g_encoded_benchmark/ --trainmachine softran4 --selection random --ctype binary
time python3 h_generate_model.py  --direncodedtraindata data/latest/g_encoded_benchmark/ --trainmachine softran4 --selection random --ctype multi

Training & Testing (Classification):
-----------------------------------
time python3 h_generate_model.py  --direncodedtraindata data/latest/g_encoded_benchmark/ --trainmachine softran4 --testmachine aparajeet --direncodedtestdata data/latest/g_encoded_production/ --selection random --ctype binary
time python3 h_generate_model.py  --direncodedtraindata data/latest/g_encoded_benchmark/ --trainmachine softran4 --testmachine aparajeet --direncodedtestdata data/latest/g_encoded_production/ --selection random --ctype multi

Testing (Classification):
------------------------
time python3 i_test_model.py --basedir data/latest --ctype binary
time python3 i_test_model.py --basedir data/latest --ctype multi
time python3 i_test_model.py --basedir data/latest --ctype multi --plot_graphs yes

Analysis (Classification):
-------------------------
time python3 -u g_analyze_data.py data/latest/f_curated_benchmark/<machinename>-<wtype>-data.json

Encoding (Regression):
----------------------
time python3 g_encode_benchmark.py --dircurateddata data/latest/f_curated_benchmark/ --direncodeddata data/latest/g_encoded_benchmark/ --wtype benchmark
time python3 g_encode_benchmark.py --dircurateddata data/latest/f_curated_production/ --direncodeddata data/latest/g_encoded_production/ --wtype production

Training & Testing (Regression):
-------------------------------
time python3 h_generate_model.py  --direncodedtraindata data/latest/g_encoded_benchmark/ --trainmachine softran4 --direncodedtestdata data/latest/g_encoded_production/ --testmachine softran4 --dirmodel data/latest/h_model/ --ctype reg --method svr_rbf


