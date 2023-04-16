#!/bin/bash

# To test this in Codespaces, run `cd /workspaces/ && rm -rf text-generation-webui && git clone https://github.com/oobabooga/text-generation-webui && WORKSPACE=/workspaces/ llm-playground/scripts/prepare_runpod.sh`
# To run this in RunPod with `runpod/oobabooga:1.0.0`, set
# Expose HTTP Ports (Max 10): 7860,8888
# docker command: `bash -c "curl https://raw.githubusercontent.com/utensil/llm-playground/main/scripts/prepare_runpod.sh -sSf | bash"`
# LOAD_MODEL PygmalionAI/pygmalion-6b
# WEBUI chatbot
# JUPYTER_PASSWORD secret
# HUGGINGFACE_TOKEN secret
# SUDO nosudo

set -euxo pipefail

set -x

WORKSPACE=${WORKSPACE:-"/workspace"}

cd $WORKSPACE

if [ ! -d "llm-playground" ]; then
  git clone https://github.com/utensil/llm-playground
fi

cd llm-playground

./helper/prepare.sh

LOAD_MODEL=${LOAD_MODEL:-"PygmalionAI/pygmalion-6b"}
LOAD_DATASET=${LOAD_DATASET:-""}

if [ ! -z "$LOAD_MODEL" ] && [ "$LOAD_MODEL" != "PygmalionAI/pygmalion-6b" ]; then
    python ./helper/download-model.py $LOAD_MODEL
fi

if [ ! -z "$LOAD_DATASET" ]; then
    python ./helper/download-dataset.py $LOAD_DATASET
fi

cd $WORKSPACE/text-generation-webui/

git pull

TMP=$WORKSPACE/tmp/
rm -rf $TMP
mkdir -p $TMP

mv models $TMP
mv loras $TMP
mv training/datasets $TMP

ln -s $WORKSPACE/llm-playground/models ./models
ln -s $WORKSPACE/llm-playground/loras ./loras
ln -s $WORKSPACE/llm-playground/datasets ./training/datasets

# comment out the following when testing in Codespaces
# if [ "$LOAD_MODEL" = "PygmalionAI/pygmalion-6b" ]; then
#     mv $TMP/models/PygmalionAI_pygmalion-6b ./models/
# fi

JUPYTER_PASSWORD=${JUPYTER_PASSWORD:-"PygmalionAI_pygmalion-6b"}

if [[ $JUPYTER_PASSWORD ]]
then
  echo "Launching Jupyter Lab"
  cd /
  nohup jupyter lab --allow-root --no-browser --port=8888 --ip=* --ServerApp.token=$JUPYTER_PASSWORD --ServerApp.allow_origin=* --ServerApp.preferred_dir=$WORKSPACE &
fi

sleep infinity