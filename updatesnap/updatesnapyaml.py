#!/usr/bin/env python3

import sys
import requests
import argparse
import base64
from SnapModule.snapmodule import Snapcraft
from SnapModule.snapmodule import Github

#project_url = sys.argv[1]
update_branch = "update_versions"

class ProjectManager(object):
    def __init__(self, user = None, token = None):
        self._github = Github(True)
        if user:
            self._github.set_secret("github", "user", user)
        if token:
            self._github.set_secret("github", "token", token)

    def join_url(self, *args):
        if len(args) == 0:
            return ""
        output = args[0]
        for element in args[1:]:
            if output[-1] == '/':
                output = output[:-1]
            if element[0] == '/':
                element = element[1:]
            output += '/' + element
        return output


    def get_working_branch(self, project_url):
        branches = self._github.get_branches(project_url)
        working_branch = 'master'
        for branch in branches:
            if branch['name'] == update_branch:
                working_branch = update_branch
                break
            # give priority to "main" over "master"
            if branch['name'] == 'main':
                working_branch = 'main'
        return working_branch


    def get_yaml_file(self, project_url, branch):
        yaml_path = "snapcraft.yaml"
        data = self._github.get_file(project_url, yaml_path)
        if not data:
            yaml_path = "snap/snapcraft.yaml"
            data = self._github.get_file(project_url, yaml_path)
            if not data:
                return None
        return data



parser = argparse.ArgumentParser(prog="Update Snap YAML",
                                 description="Find the lastest source versions for snap files and generates a new snapcraft.yaml.")
parser.add_argument('--github-user', action='store', default=None, help='User name for accesing Github projects.')
parser.add_argument('--github-token', action='store', default=None, help='Access token for accesing Github projects.')
parser.add_argument('project', default='.', help='The project URI')
arguments = parser.parse_args(sys.argv[1:])

if arguments.project == '.':
    print("A project URI is mandatory")
    sys.exit(-1)

manager = ProjectManager(arguments.github_user, arguments.github_token)

# get the most-updated SNAPCRAFT.YAML file

branch = manager.get_working_branch(arguments.project)
data = manager.get_yaml_file(arguments.project, branch)
if not data:
    print("Failed to get the snapcraft.yaml file.")
    sys.exit(-1)
contents = base64.b64decode(data["content"]).decode('utf-8')

# check for updates

snap = Snapcraft(False)
snap.load_external_data(contents)
if arguments.github_user:
    snap.set_secret("github", "user", arguments.github_user)
if arguments.github_token:
    snap.set_secret("github", "token", arguments.github_token)
updates = snap.process_parts()
