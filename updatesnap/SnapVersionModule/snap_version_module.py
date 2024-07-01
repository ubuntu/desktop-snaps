""" Processes the snap version and in the event of a new release of the primary
    component, the version number is incremented accordingly, with the package
    release number being reset to 1. Furthermore, any other modifications
    to the package result in an increment of the package release number by 1 """

import subprocess
import re
from datetime import datetime
import logging
import requests


def process_snap_version_data(upstreamversion, snap_name, version_schema, has_update):
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
    git_log_output = subprocess.run(['git', 'log', '-1', '--date=unix'],
                                    stdout=subprocess.PIPE, text=True, check=True)
    date_string = next(line for line in git_log_output.stdout.split('\n')
                       if line.startswith('Date:'))
    date_string = date_string.split(':', 1)[1].strip()

    # Convert the date string to a Unix timestamp
    gitcommitdate = int(date_string)

    prevversion = max(
        next((channel["version"] for channel in snap_info["channel-map"]
              if channel["channel"]["name"] == "stable")),
        next((channel["version"] for channel in snap_info["channel-map"]
              if channel["channel"]["name"] == "edge"))
    )

    match = re.match(version_schema, upstreamversion)
    if not match:
        logging.warning("Version schema does not match with snapping repository version")
        return None
    upstreamversion = match.group(1).replace('_', '.')

    if upstreamversion > prevversion.split('-')[0]:
        return f"{upstreamversion}-1"
    # Determine package release number
    if (gitcommitdate > snapbuilddate or has_update):
        packagerelease = int(prevversion.split('-')[-1]) + 1
    else:
        packagerelease = int(prevversion.split('-')[-1])

    return f"{upstreamversion}-{packagerelease}"


def process_rock_version_data(upstream_version, previous_version, version_schema, has_update):
    """ Returns processed rock version"""

    match = re.match(version_schema, upstream_version)
    if not match:
        logging.warning("Version schema does not match with rock repository version")
        return None
    upstream_version = match.group(1).replace('_', '.')

    upstream_tuple = tuple(map(int, upstream_version.split('.')))
    prev_tuple = tuple(map(int, previous_version.split('-')[0].split('.')))

    if upstream_tuple > prev_tuple:
        return f"{upstream_version}-1"
    # Determine package release number
    if has_update:
        packagerelease = int(previous_version.split('-')[-1]) + 1
    else:
        packagerelease = int(previous_version.split('-')[-1])

    return f"{upstream_version}-{packagerelease}"


def is_version_update(snap, manager_yaml, arguments, has_update):
    """ Returns if snap version update available """
    has_version_update = False
    if arguments.version_schema == 'None':
        return False
    metadata = snap.process_metadata()
    if process_snap_version_data(metadata['upstream-version'], metadata['name'],
                                 arguments.version_schema, has_update) is not None:
        snap_version = process_snap_version_data(
            metadata['upstream-version'], metadata['name'], arguments.version_schema, has_update)
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


def is_rock_version_update(rock, manager_yaml, arguments, has_update):
    """ Returns if rock version update available """
    has_version_update = False
    if arguments.rock_version_schema == 'None':
        return False
    metadata = rock.process_metadata()
    rock_version = process_rock_version_data(metadata['upstream-version'], metadata['version'],
                                             arguments.rock_version_schema, has_update)
    if rock_version is None:
        return False
    if metadata['version'] != rock_version:
        rock_version_data = manager_yaml.get_part_metadata('version')
        if rock_version_data is not None:
            logging.info("Updating rock version from %s to %s",
                         metadata['version'], rock_version)
            rock_version_data['data'] = f"version: '{rock_version}'"
            has_version_update = True
        else:
            logging.warning("Version is not defined in metadata")

    if has_version_update:
        with open('version_file', 'w', encoding="utf8") as version_file:
            version_file.write(f"{rock_version}")

    return has_version_update
