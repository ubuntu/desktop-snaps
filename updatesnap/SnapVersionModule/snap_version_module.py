""" Processes the snap version and in the event of a new release of the primary
    component, the version number is incremented accordingly, with the package
    release number being reset to 1. Furthermore, any other modifications
    to the package result in an increment of the package release number by 1 """

import subprocess
import os
import shutil
import re
from datetime import datetime
import logging
import requests
import git


def process_snap_version_data(git_repo_url, snap_name, version_schema):
    """ Returns processed snap version and grade """

    # Time stamp of Snap build in Snap Store
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

    # Time stamp of the last GIT commit of the snapping repository
    os.chdir('..')
    git_log_output = subprocess.run(['git', 'log', '-1', '--date=unix'],
                                    stdout=subprocess.PIPE, text=True, check=True)
    date_string = next(line for line in git_log_output.stdout.split('\n')
                       if line.startswith('Date:'))
    date_string = date_string.split(':', 1)[1].strip()

    # Convert the date string to a Unix timestamp
    gitcommitdate = int(date_string)
    os.chdir('desktop-snaps/')

    prevversion = max(
        next((channel["version"] for channel in snap_info["channel-map"]
              if channel["channel"]["name"] == "stable")),
        next((channel["version"] for channel in snap_info["channel-map"]
              if channel["channel"]["name"] == "edge"))
    )
    # Clone the leading upstream repository if it doesn't exist
    repo_dir = os.path.basename(git_repo_url.rstrip('.git'))
    if not os.path.exists(repo_dir):
        try:
            git.Repo.clone_from(git_repo_url, repo_dir)
        except git.exc.GitError:
            logging.warning('Some error occur in cloning leading upstream repo')
            os.chdir('..')
            return None

    os.chdir(repo_dir)

    upstreamversion = subprocess.run(["git", "describe", "--tags", "--always"],
                                     stdout=subprocess.PIPE,
                                     text=True, check=True).stdout.strip()
    os.chdir('..')
    shutil.rmtree(repo_dir)
    match = re.match(version_schema, upstreamversion)
    if not match:
        logging.warning("Version schema does not match with snapping repository version")
        return None
    upstreamversion = match.group(1).replace('_', '.')

    if upstreamversion != prevversion:
        return f"{upstreamversion}-1"
    # Determine package release number
    packagerelease = int(
        prevversion.split('-')[-1]) + 1 if gitcommitdate > snapbuilddate \
        else prevversion.split('-')[-1]

    return f"{upstreamversion}-{packagerelease}"


def is_version_update(snap, manager_yaml, arguments):
    """ Returns if snap version update available """
    has_version_update = False
    if arguments.version_schema == 'None':
        return False
    metadata = snap.process_metadata()
    if process_snap_version_data(metadata['upstream-url'],
                                 metadata['name'], arguments.version_schema) is not None:
        snap_version = process_snap_version_data(
            metadata['upstream-url'], metadata['name'], arguments.version_schema)
        if metadata['version'] != snap_version:
            snap_version_data = manager_yaml.get_part_metadata('version')
            if snap_version_data is not None:
                logging.info("Updating snap version from %s to %s",
                             metadata['version'], snap_version)
                snap_version_data['data'] = f"version: '{snap_version}'"
                has_version_update = True
            else:
                logging.warning("Version is not defined in metadata")

    if has_version_update:
        with open('version_file', 'w', encoding="utf8") as version_file:
            version_file.write(f"{snap_version}")

    return has_version_update
