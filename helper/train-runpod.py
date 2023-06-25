import importlib
import fire
import yaml
import logging
import os
import sys
from pathlib import Path
from addict import Dict
import json
import time
import runpod
from datetime import datetime, timezone, timedelta

AXOLOTL_RUNPOD_IMAGE = 'winglian/axolotl-runpod:main-py3.9-cu118-2.0.0'
DEFAULT_TEMPLATE_ID = '758uq6u5fc'
MAX_BID_PER_GPU = 2.0

POLL_PERIOD = 5 # 5 seconds
MAX_WAIT_TIME = 60 * 10 # 10 minutes

DEFAULT_TERMINATE_AFTER = 60 * 15 # 15 minutes to prevent accidental starting a pod and forgot to terminate

class DictDefault(Dict):
    """
    A Dict that returns None instead of returning empty Dict for missing keys.
    Borrowed from https://github.com/utensil/axolotl/blob/local_dataset/src/axolotl/utils/dict.py
    """

    def __missing__(self, key):
        return None

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

os.chdir(project_root)

# src_dir = os.path.join(project_root, "src")
# sys.path.insert(0, src_dir)

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

# os.environ["RUNPOD_DEBUG"] = 'true'

def train_on_runpod(
    config,
    **kwargs,
):
    config = Path(config.strip())
    logging.info(f"Train on runpod with config: {config}")

    # load the config from the yaml file
    # Mostly borrowed from https://github.com/utensil/axolotl/blob/local_dataset/scripts/finetune.py
    with open(config, encoding="utf-8") as file:
        cfg: DictDefault = DictDefault(yaml.safe_load(file))

        # if there are any options passed in the cli, if it is something that seems valid from the yaml,
        # then overwrite the value
        cfg_keys = cfg.keys()
        for k, _ in kwargs.items():
            # if not strict, allow writing to cfg even if it's not in the yml already
            if k in cfg_keys or not cfg.strict:
                # handle booleans
                if isinstance(cfg[k], bool):
                    cfg[k] = bool(kwargs[k])
                else:
                    cfg[k] = kwargs[k]

        # get the runpod config
        runpod_cfg = cfg.pop('runpod', None)

        if runpod_cfg is None:
            raise ValueError("No pod config found in config file")
        
        runpod_api_key = os.getenv("RUNPOD_API_KEY")

        if runpod_api_key is None:
            raise ValueError("No RUNPOD_API_KEY environment variable found")
        
        runpod.api_key = runpod_api_key

        gpu = runpod_cfg.gpu or "NVIDIA RTX A5000"

        gpu_info = runpod.get_gpu(gpu)

        # TODO: warn if the bid is too high
        bid_per_gpu = min(gpu_info['lowestPrice']['minimumBidPrice'], runpod_cfg.max_bid_per_gpu or MAX_BID_PER_GPU)

        env = runpod_cfg.env or {}
        env['TRAINING_CONFIG'] = str(config)

        entry = None
        
        if runpod_cfg.entry is not None:
            # TODO: a better way to escape the entry
            entry = json.dumps(runpod_cfg.entry)[1:-1]

        terminate_after = (datetime.now(timezone.utc) + timedelta(seconds=runpod_cfg.terminate_after or DEFAULT_TERMINATE_AFTER)).strftime('"%Y-%m-%dT%H:%M:%SZ"')

        pod = runpod.create_spot_pod(f'Training {config}',
                                     AXOLOTL_RUNPOD_IMAGE,
                                     gpu,
                                     cloud_type=runpod_cfg.cloud_type or "SECURE",
                                     bid_per_gpu=bid_per_gpu,
                                     template_id=runpod_cfg.template_id or DEFAULT_TEMPLATE_ID,
                                     gpu_count=runpod_cfg.gpu_count or 1,
                                     min_vcpu_count=runpod_cfg.min_vcpu_count or 8,
                                     min_memory_in_gb=runpod_cfg.min_memory_in_gb or 29,
                                     min_download=runpod_cfg.min_download or 2000,
                                     min_upload=runpod_cfg.min_upload or 1500,
                                     docker_args=entry,
                                     env=env,
                                     terminate_after=terminate_after
                                     )
        
        if pod is None:
            logging.error(f"Failed to create pod for {config}")
            return
        
        logging.info(f"Created pod {pod['id']}, waiting for it to start...(at most {MAX_WAIT_TIME} seconds)")
        logging.info(f" - While you're waiting, you can check the status of the pod at https://www.runpod.io/console/pods ")
        username = pod['machine']['podHostId']
        ssh_command = f'ssh {username}@ssh.runpod.io -i ~/.ssh/id_ed25519'
        logging.info(f" - After started, use the following command to ssh into the pod: {ssh_command}")          

        try:        
            # wait for the pod to start
            pod_info = None
            runtime = None
            waited_time = 0
            is_debug = os.getenv("RUNPOD_DEBUG") or ''
            os.environ["RUNPOD_DEBUG"] = ''
            while runtime is None and waited_time < MAX_WAIT_TIME:
                pod_info = runpod.get_pod(pod['id'])
                runtime = pod_info['pod']['runtime']
                time.sleep(POLL_PERIOD)
                waited_time += POLL_PERIOD
            os.environ["RUNPOD_DEBUG"] = is_debug

            if runtime is None:
                logging.error(f"Pod {pod['id']} failed to start: {pod_info}")
                runpod.terminate_pod(pod['id'])
                logging.info(f"Pod {pod['id']} terminated")

            logging.info(f"Pod {pod['id']} started: {pod_info}")  
        except Exception as ex:
            logging.error(f"Something went wrong with {pod['id']}: {ex}")
            runpod.terminate_pod(pod['id'])
            logging.info(f"Pod {pod['id']} terminated")

if __name__ == "__main__":
    fire.Fire(train_on_runpod)