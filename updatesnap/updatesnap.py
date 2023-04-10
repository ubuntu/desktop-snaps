#!/usr/bin/env python3

""" Analizes a YAML file and shows the available updates for each part """

import argparse
import sys
import os
import requests
from SnapModule.snapmodule import Snapcraft

def apply_local_secrets(snap, arguments):
    """ Sets the github user and token in the snap processor object """

    if arguments.github_user:
        snap.set_secret("github", "user", arguments.github_user)
    if arguments.github_token:
        snap.set_secret("github", "token", arguments.github_token)


def process_folder(folder_path, arguments):
    """ Processes a folder, searching for the snapcraft.yaml files """

    snap = Snapcraft(arguments.s)
    snap.load_local_file(folder_path)
    apply_local_secrets(snap, arguments)
    if len(arguments.parts) >= 1:
        retdata = []
        for part in arguments.parts:
            retdata.append(snap.process_part(part))
        return retdata
    return snap.process_parts()


def process_data(data, arguments):
    """ Processed a YAML data passed in the data argument """

    snap = Snapcraft(arguments.s)
    snap.load_external_data(data)
    apply_local_secrets(snap, arguments)
    if len(arguments.parts) >= 1:
        retdata = []
        for part in arguments.parts:
            retdata.append(snap.process_part(part))
        return retdata
    return snap.process_parts()


def print_summary(data):
    """ Prints the results of the process, specifying which parts have
        new versions available """
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
        print(f"{entry['name']} current version: {entry['version'][0]}\
 ({entry['version'][1]}); available updates:")
        for update in entry["updates"]:
            print(f"    {update['name']} (tagged at {update['date']})")


def main():
    """ Main function """
    parser = argparse.ArgumentParser(prog="Update Snap",
                                    description="Find the lastest source versions for snap files.")
    parser.add_argument('-s', action='store_true', help='Silent output.')
    parser.add_argument('-r', action='store_true',
                        help='Process all the snaps recursively '
                        'from the specified folder.')
    parser.add_argument('--github-user', action='store',
                        help='User name for accesing Github projects.')
    parser.add_argument('--github-token', action='store',
                        help='Access token for accesing Github projects.')
    parser.add_argument('folder', default='.', help='The folder of the snapcraft project.')
    parser.add_argument('parts', nargs='*', help='A list of parts to check.')
    argument_list = parser.parse_args(sys.argv[1:])

    if argument_list.r: # recursive
        if (argument_list.folder.startswith("http://") or
            argument_list.folder.startswith("https://")):
            print("-r parameter can't be used with http or https. Aborting.")
            sys.exit(-1)
        retval = []
        for folder in os.listdir(argument_list.folder):
            full_path = os.path.join(argument_list.folder, folder)
            if not os.path.isdir(full_path):
                continue
            retval += process_folder(full_path, argument_list)
    else:
        if ((not argument_list.folder.startswith("http://")) and
        (not argument_list.folder.startswith("https://"))):
            retval = process_folder(argument_list.folder, argument_list)
        else:
            response = requests.get(argument_list.folder)
            if not response:
                print(f"Failed to get the file {argument_list.folder}: {response.status_code}")
                sys.exit(-1)
            retval = process_data(response.content.decode('utf-8'), argument_list)
    print_summary(retval)

if __name__ == "__main__":
    main()
