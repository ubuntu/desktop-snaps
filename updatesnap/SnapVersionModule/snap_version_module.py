""" Extends ManageYAML and Snapcraft from snpamodule
    and introduces two functions process_snap_version_data
    and is_version_update to support auto snap versioning"""

import subprocess
import os
import shutil
import re
from datetime import datetime
from typing import Optional
import requests
import git
from SnapModule.snapmodule import ManageYAML, Snapcraft


class ExtendedSnapcraft(Snapcraft):
    """ Extends Snapcraft to introduces new function process_metadata """
    def process_metadata(self) -> Optional[dict]:
        """ Returns metadata from Snapcraft.yaml file """
        metadata = {
            "name": None,
            "version": None,
            "adopt-info": None,
            "grade": None,
            "upstream-version": None,
            "upstream-url": None,
        }

        if self._config is None:
            return None
        data = self._config

        if 'name' in data:
            metadata['name'] = data['name']

        if 'version' in data:
            metadata['version'] = data['version']
        if 'adopt-info' in data:
            metadata['adopt-info'] = data['adopt-info']
            upstream_data = self.process_part(data['adopt-info'])
            metadata['upstream-url'] = upstream_data['source_url']
            if len(upstream_data['updates']) != 0:
                metadata['upstream-version'] = upstream_data['updates'][0]

        if 'grade' in data:
            metadata['grade'] = data['grade']
        return metadata


class ExtendedManageYAML(ManageYAML):
    """ Extends ManageYAML to introduce functions which process metadata """
    def get_metadata(self) -> Optional[dict]:
        """ Returns metadata in form of list """
        data = []
        for entry in self._tree:
            if entry['data'] == 'part':
                continue
            data.append(entry)
        return data

    def get_part_metadata(self, element: str) -> Optional[dict]:
        """ Returns specific element of the metadata"""
        metadata = self.get_metadata()
        if metadata:
            for entry in metadata:
                if entry['data'].startswith(element):
                    return entry
        return None


def process_snap_version_data(git_repo_url, snap_name, version_schema):
    """ Returns processed snap version and grade """

    # Time stamp of Snap build in Snap Store
    # snap_info_url = f"https://api.snapcraft.io/v2/snaps/info/{snap_name}"
    response = requests.get(f"https://api.snapcraft.io/v2/snaps/info/{snap_name}",
                            headers={"Snap-Device-Series": "16", }, timeout=20)
    snap_info = response.json()

    edge_channel_info = next((channel for channel in snap_info["channel-map"]
                              if channel["channel"]["name"] == "edge"
                              and channel["channel"]["architecture"] == "amd64"), None)
    snapbuilddate = 0
    if edge_channel_info:
        # Parse the date string using datetime
        snapbuilddate = datetime.fromisoformat(edge_channel_info["created-at"]
                                               .replace("Z", "+00:00"))
        snapbuilddate = int(snapbuilddate.timestamp())

    # Clone the repository if it doesn't exist
    repo_dir = os.path.basename(git_repo_url.rstrip('.git'))
    if not os.path.exists(repo_dir):
        try:
            git.Repo.clone_from(git_repo_url, repo_dir)
        except git.exc.GitError:
            print('Some error occur in cloning snapping repo')
            os.chdir('..')
            return None

    os.chdir(repo_dir)

    # Time stamp of the last GIT commit of the snapping repository
    repo = git.Repo('.')
    last_commit = repo.head.commit
    gitcommitdate = int(last_commit.authored_date)

    # # Previous stable and development version
    # prevstable = snap_info["channel-map"][0][
    #     "version"]  # Assuming "stable" is the first channel in the response
    # prevdevel = snap_info["channel-map"][1][
    #     "version"]  # Assuming "edge" is the second channel in the response
    prevversion = max(snap_info["channel-map"][0]["version"],
                      snap_info["channel-map"][1]["version"])

    upstreamversion = subprocess.run(["git", "describe", "--tags", "--always"],
                                     stdout=subprocess.PIPE,
                                     text=True, check=True).stdout.strip()
    os.chdir('..')
    shutil.rmtree(repo_dir)
    match = re.match(version_schema, upstreamversion)
    if not match:
        print("Version schema does not match with snapping repository version")
        return None
    upstreamversion = match.group(1)

    # Determine package release number
    packagerelease = int(
        prevversion.split('-')[-1]) + 1 if gitcommitdate > snapbuilddate else 1

    return f"{upstreamversion}-{packagerelease}", "stable"


def is_version_update(snap, manager_yaml, arguments):
    """ Returns if snap version update available """
    has_version_update = False
    if arguments.version_schema == 'None':
        return False
    metadata = snap.process_metadata()
    if process_snap_version_data(metadata['upstream-url'],
                                 metadata['name'], arguments.version_schema) is not None:
        snap_version, snap_grade = process_snap_version_data(
            metadata['upstream-url'], metadata['name'], arguments.version_schema)
        if metadata['version'] != snap_version:
            snap_version_data = manager_yaml.get_part_metadata('version')
            if snap_version_data is not None:
                print(f"Updating snap version from {metadata['version']} to {snap_version}")
                snap_version_data['data'] = f"version: '{snap_version}'"
                has_version_update = True
            else:
                print("Version is not defined in metadata")
        if metadata['grade'] != snap_grade:
            snap_grade_data = manager_yaml.get_part_metadata('grade')
            if snap_grade_data is not None:
                print(f"Updating snap grade from {metadata['grade']} to {snap_grade}")
                snap_grade_data['data'] = f"grade: '{snap_grade}'"
                has_version_update = True
            else:
                print("Grade is not defined in metadata")
    if has_version_update:
        with open('version_file', 'w', encoding="utf8") as version_file:
            version_file.write(f"{snap_version}")

    return has_version_update
