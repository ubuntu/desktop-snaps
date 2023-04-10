#!/usr/bin/env python3

""" Analizes a YAML file and outputs  """

import sys
import argparse
import base64
from SnapModule.snapmodule import Snapcraft
from SnapModule.snapmodule import Github
from SnapModule.snapmodule import ManageYAML

UPDATE_BRANCH = 'update_versions'

class ProjectManager:
    """ This class is the one that searches in a remote project for
        the corresponding snapcraft.yaml file """
    def __init__(self, user = None, token = None):
        """ Constructor. """
        self._github = Github(True)
        if user:
            self._github.set_secret('user', user)
        if token:
            self._github.set_secret('token', token)


    def get_working_branch(self, project_url):
        """ Returns the main branch of the project """

        branches = self._github.get_branches(project_url)
        working_branch = 'master'
        for branch in branches:
            if branch['name'] == UPDATE_BRANCH:
                working_branch = UPDATE_BRANCH
                break
            # give priority to 'main' over 'master'
            if branch['name'] == 'main':
                working_branch = 'main'
            # give priority to 'stable' over any other
            if branch['name'] == 'stable':
                working_branch = 'stable'
                break
        return working_branch


    def get_yaml_file(self, project_url):
        """ Searches in a project for the 'snapcraft.yaml' file and
            returns its contents """
        yaml_path = 'snapcraft.yaml'
        data = self._github.get_file(project_url, yaml_path)
        if not data:
            yaml_path = 'snap/snapcraft.yaml'
            data = self._github.get_file(project_url, yaml_path)
            if not data:
                return None
        return data

def main():
    """ Main code """
    parser = argparse.ArgumentParser(prog='Update Snap YAML',
                                    description='Find the lastest source'
                                    ' versions for snap files and generates a new snapcraft.yaml.')
    parser.add_argument('--github-user', action='store', default=None,
                        help='User name for accesing Github projects.')
    parser.add_argument('--github-token', action='store', default=None,
                        help='Access token for accesing Github projects.')
    parser.add_argument('project', default='.', help='The project URI')
    arguments = parser.parse_args(sys.argv[1:])

    if arguments.project == '.':
        print('A project URI is mandatory')
        sys.exit(-1)

    manager = ProjectManager(arguments.github_user, arguments.github_token)

    # get the most-updated SNAPCRAFT.YAML file

    #branch = manager.get_working_branch(arguments.project)
    data = manager.get_yaml_file(arguments.project)
    if not data:
        print('Failed to get the snapcraft.yaml file.')
        sys.exit(-1)
    contents = base64.b64decode(data['content']).decode('utf-8')

    manager_yaml = ManageYAML(contents)

    snap = Snapcraft(True)
    snap.load_external_data(contents)
    if arguments.github_user:
        snap.set_secret('github', 'user', arguments.github_user)
    if arguments.github_token:
        snap.set_secret('github', 'token', arguments.github_token)
    parts = snap.process_parts()

    if len(parts) == 0:
        print("The snapcraft.yaml file has no parts.")
        sys.exit(0) # no parts

    has_update = False
    for part in parts:
        if not part:
            continue
        if not part['updates']:
            continue
        version_data = manager_yaml.get_part_element(part['name'], 'source-tag:')
        if not version_data:
            continue
        print(f"Updating '{part['name']}' from version '{part['version'][0]}'"
            " to version '{part['updates'][0]['name']}'")
        version_data['data'] = f"source-tag: '{part['updates'][0]['name']}'"
        has_update = True

    if has_update:
        print("\n\n")
        print(manager_yaml.get_yaml())
    else:
        print("No updates available")

if __name__ == "__main__":
    main()
