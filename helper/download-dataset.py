'''
Downloads datasets from Hugging Face to datasets/dataset-name.

Example:
python download-dataset.py tatsu-lab/alpaca

NOTE: this file is based on `download-model.py` and heavily modified

'''

import argparse
import base64
import datetime
import json
import re
import sys
from pathlib import Path
import subprocess

import requests
import tqdm
from tqdm.contrib.concurrent import thread_map

parser = argparse.ArgumentParser()
parser.add_argument('DATASET', type=str, default=None, nargs='?')
parser.add_argument('--threads', type=int, default=1, help='Number of files to download simultaneously.')
parser.add_argument('--output', type=str, default=None, help='The folder where the dataset should be saved.')
args = parser.parse_args()

def get_file(url, output_folder):
    r = requests.get(url, stream=True)
    with open(output_folder / Path(url.rsplit('/', 1)[1]), 'wb') as f:
        total_size = int(r.headers.get('content-length', 0))
        block_size = 1024
        with tqdm.tqdm(total=total_size, unit='iB', unit_scale=True, bar_format='{l_bar}{bar}| {n_fmt:6}/{total_fmt:6} {rate_fmt:6}') as t:
            for data in r.iter_content(block_size):
                t.update(len(data))
                f.write(data)

def get_file_by_aria2(url, output_folder):
    filename = url.split('/')[-1]

    print(f"aria2c --console-log-level=error -c -x 16 -s 16 -k 1M {url} -d {output_folder}")
    # r = requests.get(url, stream=True)
    # total_size = int(r.headers.get('content-length', 0))
    
    if (output_folder / Path(filename)).exists() and not (output_folder / Path(f"{filename}.aria2")).exists():
        print(f"File {filename} already downloaded.")
        return

    # # call command line aria2c to download
    subprocess.run(f"aria2c -c -x 16 -s 16 -k 1M {url} -d {output_folder} -o {filename}", shell=True, check=True)

def sanitize_branch_name(branch_name):
    pattern = re.compile(r"^[a-zA-Z0-9._-]+$")
    if pattern.match(branch_name):
        return branch_name
    else:
        raise ValueError("Invalid branch name. Only alphanumeric characters, period, underscore and dash are allowed.")

def get_download_links_from_huggingface(dataset, branch):
    base = "https://huggingface.co"
    page = f"/api/datasets/{dataset}/tree/{branch}?cursor="
    cursor = b""

    links = []
    sha256 = []
    classifications = []
    has_pytorch = False
    has_pt = False
    has_safetensors = False
    is_lora = False
    while True:
        content = requests.get(f"{base}{page}{cursor.decode()}").content

        dict = json.loads(content)
        if len(dict) == 0:
            break

        for i in range(len(dict)):
            fname = dict[i]['path']

            if 'lfs' in dict[i]:
                sha256.append([fname, dict[i]['lfs']['oid']])

            links.append(f"https://huggingface.co/{dataset}/resolve/{branch}/{fname}")

        cursor = base64.b64encode(f'{{"file_name":"{dict[-1]["path"]}"}}'.encode()) + b':50'
        cursor = base64.b64encode(cursor)
        cursor = cursor.replace(b'=', b'%3D')

    return links, sha256

def download_files(file_list, output_folder, num_threads=8):
    thread_map(lambda url: get_file_by_aria2(url, output_folder), file_list, max_workers=num_threads)

if __name__ == '__main__':
    dataset = args.DATASET
    branch = args.branch
    if dataset is None:
        print("Error: Please specify a dataset to download.")
        sys.exit()
    else:
        if dataset[-1] == '/':
            dataset = dataset[:-1]
            branch = args.branch
        if branch is None:
            branch = "main"
        else:
            try:
                branch = sanitize_branch_name(branch)
            except ValueError as err_branch:
                print(f"Error: {err_branch}")
                sys.exit()

    links, sha256, is_lora = get_download_links_from_huggingface(dataset, branch)

    if args.output is not None:
        base_folder = args.output
    else:
        base_folder = 'datasets' if not is_lora else 'loras'

    output_folder = f"{'_'.join(dataset.split('/')[-2:])}"
    if branch != 'main':
        output_folder += f'_{branch}'

    # Creating the folder and writing the metadata
    output_folder = Path(base_folder) / output_folder
    if not output_folder.exists():
        output_folder.mkdir()
    with open(output_folder / 'huggingface-metadata.txt', 'w') as f:
        f.write(f'url: https://huggingface.co/{dataset}\n')
        f.write(f'branch: {branch}\n')
        f.write(f'download date: {str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))}\n')
        sha256_str = ''
        for i in range(len(sha256)):
            sha256_str += f'    {sha256[i][1]} {sha256[i][0]}\n'
        if sha256_str != '':
            f.write(f'sha256sum:\n{sha256_str}')

    # Downloading the files
    print(f"Downloading the dataset to {output_folder}")
    download_files(links, output_folder, args.threads)
    print()

