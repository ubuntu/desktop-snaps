#!/usr/bin/env python3

import argparse
import pathlib
import sys
from SnapModule.snapmodule import Snapcraft

def apply_local_secrets(snap):
    global arguments
    if arguments.github_user:
        snap.set_secret("github", "user", arguments.github_user)
    if arguments.github_token:
        snap.set_secret("github", "token", arguments.github_token)
    return


def process_folder(folder):
    global arguments

    snap = Snapcraft(arguments.s)
    snap.load_local_file(folder)
    apply_local_secrets(snap);
    if len(arguments.parts) >= 1:
        retdata = []
        for a in arguments.parts:
            retdata.append(snap.process_part(a))
        return retdata
    else:
        return snap.process_parts()


def process_data(data):
    global arguments

    snap = Snapcraft(arguments.s)
    snap.load_external_data(data)
    apply_local_secrets(snap)
    if len(arguments.parts) >= 1:
        retdata = []
        for a in arguments.parts:
            retdata.append(snap.process_part(a))
        return retdata
    else:
        return snap.process_parts()


def print_summary(data):
    printed_line = False
    for entry in data:
        if entry is None:
            continue
        if printed_line:
            print()
            printed_line = False
        if entry["missing_format"]:
            print(f"{entry['name']}: needs version format definition.")
            printed_line = True
        if entry["use_branch"]:
            print(f"{entry['name']}: uses branch instead of tag.")
            printed_line = True
        if not entry["use_branch"] and not entry["use_tag"]:
            print(f"{entry['name']}: has not defined tag or branch to use.")
            printed_line = True
        if len(entry["updates"]) == 0:
            continue
        printed_line = True
        print(f"{entry['name']} current version: {entry['version'][0]} ({entry['version'][1]}); available updates:")
        for update in entry["updates"]:
            print(f"    {update['name']} (tagget at {update['date']})")


parser = argparse.ArgumentParser(prog="Update Snap",
                                 description="Find the lastest source versions for snap files.")
parser.add_argument('-s', action='store_true', help='Silent output.')
parser.add_argument('-r', action='store_true', help='Process all the snaps recursively from the specified folder.')
parser.add_argument('--github-user', action='store', help='User name for accesing Github projects.')
parser.add_argument('--github-token', action='store', help='Access token for accesing Github projects.')
parser.add_argument('folder', default='.', help='The folder of the snapcraft project.')
parser.add_argument('parts', nargs='*', help='A list of parts to check.')
arguments = parser.parse_args(sys.argv[1:])

if arguments.r: # recursive
    if arguments.folder.startswith("http://") or arguments.folder.startswith("https://"):
        print(f"-r parameter can't be used with http or https. Aborting.")
        sys.exit(-1)
    retval = []
    for folder in os.listdir(arguments.folder):
        full_path = os.path.join(arguments.folder, folder)
        if not os.path.isdir(full_path):
            continue
        retval += process_folder(full_path)
else:
    if (not arguments.folder.startswith("http://")) and (not arguments.folder.startswith("https://")):
        retval = process_folder(arguments.folder)
    else:
        response = requests.get(arguments.folder)
        if not response:
            print(f"Failed to get the file {arguments.folder}: {response.status_code}")
            sys.exit(-1)
        retval = process_data(response.content.decode('utf-8'))
print_summary(retval)
