#!/bin/bash
#
# Container source: https://github.com/OpenAccess-AI-Collective/axolotl/blob/main/docker/Dockerfile-runpod
#
#
# To run this in RunPod with `winglian/axolotl-runpod:main-py3.9-cu118-2.0.0`, set
# Expose HTTP Ports (Max 10): 7860,8888
# docker command: `bash -c "curl -H 'Cache-Control: no-cache' https://raw.githubusercontent.com/utensil/llm-playground/main/scripts/entry/ax_lite.sh -sSf | bash"`
# JUPYTER_PASSWORD change to your secret
# HUGGINGFACE_TOKEN change to your token from https://huggingface.co/settings/tokens
# WORKSPACE /workspace/
# WANDB_API_KEY change to your key from https://wandb.ai/authorize
#
# MUST mount volume disk at /content/
#
# To test this in Codespaces, run `cd /workspaces/ && WORKSPACE=/workspaces/ llm-playground/scripts/entry/ax_lite.sh`

set -euxo pipefail

set -x

WORKSPACE=${WORKSPACE:-"/workspace"}

export DEBIAN_FRONTEND=noninteractive

# make the cache live on volume disk
rm -rf /root/.cache
mkdir -p /content/cache
ln -s /content/cache /root/.cache

# prepare jupyter
pip install jupyterhub notebook jupyterlab jupyterlab-git ipywidgets

# prepare monitoring GPU
pip install nvitop

# update axolotl
cd $WORKSPACE
if [ ! -d "axolotl-update" ]; then
  git clone https://github.com/OpenAccess-AI-Collective/axolotl axolotl-update
# don't update between run yet
# else
#   cd axolotl-update && git pull && cd ..
fi
cp -r axolotl-update/* axolotl
cd axolotl
# but don't install yet
# pip install -e .

mkdir -p /content/
cd /content/
if [ ! -d "llm-playground" ]; then
  git clone https://github.com/utensil/llm-playground
# don't update between run yet
# else
#   cd llm-playground && git pull && cd ..
fi

# update h2ogpt
cd /content/
if [ ! -d "h2ogpt-update" ]; then
  git clone https://github.com/h2oai/h2ogpt.git h2ogpt-update
# don't update between run yet
# else
#   cd h2ogpt-update && git pull && cd ..
fi
cp -r h2ogpt-update/* h2ogpt
cd h2ogpt
# but don't install yet
# pip install -e .

cd /content/
if [ ! -d "h2ogpt" ]; then
  git clone https://github.com/h2oai/h2ogpt.git
# don't update between run yet
# else
#   cd h2ogpt && git pull && cd ..
fi

cd $WORKSPACE

# don't update peft
# PEFT_COMMIT_HASH=${PEFT_COMMIT_HASH:-"main"}
# pip install git+https://github.com/huggingface/peft.git@$PEFT_COMMIT_HASH

JUPYTER_PASSWORD=${JUPYTER_PASSWORD:-"ernest"}

echo "Launching Jupyter Lab with nohup..."
cd /
nohup jupyter lab --allow-root --no-browser --port=8888 --ip=* --ServerApp.token=$JUPYTER_PASSWORD --ServerApp.allow_origin=* --ServerApp.preferred_dir=$WORKSPACE &

sleep infinity
