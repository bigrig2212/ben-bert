#!/usr/bin/env bash
NUMBER_OF_PROCS=$(nproc)
NUMBER_OF_PROCS=$(($NUMBER_OF_PROCS-1))
#bert-serving-start -model_dir models/uncased_L-12_H-768_A-12 -graph_tmp_dir ${PROJECT_HOME}/tmp  -num_worker=${NUMBER_OF_PROCS} -http_port 8125 -http_max_connect 20 -show_tokens_to_client > ${PROJECT_HOME}/logs/bert-server.log
#UNCASED
#bert-serving-start -http_port 8125 -num_worker=${NUMBER_OF_PROCS} -model_dir models/uncased_L-12_H-768_A-12
#MULTILINGUAL
bert-serving-start -http_port 8080 -num_worker=${NUMBER_OF_PROCS} -model_dir models/uncased_L-12_H-768_A-12
