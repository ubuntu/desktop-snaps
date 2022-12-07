#!/usr/bin/python3
import argparse
import json
import requests
import subprocess
import sys
import urllib.request
import yaml

from launchpadlib.launchpad import Launchpad
from launchpadlib.credentials import AuthorizeRequestTokenWithURL

STORE_URL = "https://api.snapcraft.io/api/v1/snaps/details/{snap}?channel={channel}"
STORE_HEADERS = {"X-Ubuntu-Series": "16", "X-Ubuntu-Architecture": "{arch}"}

parser = argparse.ArgumentParser()
parser.add_argument(
    "-b", "--branch", help="Upstream branch to check", default="stable",
)
parser.add_argument(
    "-c", "--channel", help="channel for the snap", default="candidate",
)
parser.add_argument(
    "-l", "--lpurl", help="launchpad url for the snap build",
)
parser.add_argument(
    "-n", "--name", help="snap name in the store",
)
parser.add_argument(
    "-s", "--serie", help="ubuntu serie to use for the build", default="focal",
)
parser.add_argument(
    "-v", "--vcs", help="Upstream vcs url",
)
arg = parser.parse_args()

branch = arg.branch
source = arg.vcs

print(arg.name)
def store_parse_versions(package):
    """Build a dictionnary of the channels and versions of a snap in the store"""
    result = {}
    # the store wants a Snap-Device-Series header
    req = urllib.request.Request(
        "http://api.snapcraft.io/v2/snaps/info/%s" % package,
        headers={"Content-Type": "application/json", "Snap-Device-Series": "16"},
    )
    snapdetails = urllib.request.urlopen(req)
    report = json.load(snapdetails)
    for items in report["channel-map"]:
        larch = items["channel"]["architecture"]
        lchannel = items["channel"]["name"]
        version = items["version"]
        if larch not in result:
            result[larch] = {}
        result[larch][lchannel] = version
    return result

def launchpadlib_parse_snapinfo(launchpad, url):
    """Query launchpad for the snap details"""
    arches_get_status = []
    snapinfo = {}
    branch = None
    logurl = None

    # use a proper api compatible url
    url = url.replace('https://code.launchpad.net/', 'https://api.launchpad.net/devel/')
    url = url.replace('https://launchpad.net/', 'https://api.launchpad.net/devel/')
    snapobj = launchpad.load(url)
   
    gitref = snapobj.git_ref
    if gitref:
        snapinfo['branch'] = (gitref.path.split('/')[-1], gitref.web_link)
    if snapobj.distro_series:
        snapinfo['serie'] = snapobj.distro_series.name
    snapinfo['name'] = snapobj.name
    snapinfo['owner'] = snapobj.owner.name

    for cpu in snapobj.processors:
        arches_get_status.append(cpu.name)

    for build in snapobj.builds:
        if build.arch_tag in arches_get_status:
            arches_get_status.remove(build.arch_tag)
        else:
            continue

        if build.buildstate =='Successfully built':
            status = 'B'
        else:
            status = 'F'

        snapinfo[build.arch_tag]=(status, build.build_log_url)

        # we got the build status for the arches we wanted so return
        if not arches_get_status:
            return snapinfo
    return snapinfo

# Get the current store versions
snapbuilds = store_parse_versions(arg.name)

# Get the current upstream id
gitver = subprocess.check_output(["git", "ls-remote", source, branch], encoding="UTF-8").split()[0][:8]

buildrecords = None
channel = arg.channel

for buildarch in snapbuilds:
    # Check if there is a build in the channel we are interested in
    if channel not in snapbuilds[buildarch]:
        # special case stable, even if there is no candidate build we still want to build there
        if channel == 'candidate' and 'stable' in snapbuilds[buildarch]:
            channel = 'stable'
        else:
            continue
    
    # Check if the snap version is current with upstream
    if gitver not in snapbuilds[buildarch][channel]:
        # Use launchpadlib to query builds record
        if not buildrecords:
            launchpad = Launchpad.login_with('desktop-snaps-rebuild', service_root='production', version='devel', consumer_name='desktop-snaps-rebuild', credentials_file="launchpad", authorization_engine=AuthorizeRequestTokenWithURL('production', consumer_name='desktop-snaps-rebuild'))
            snapinfo = launchpadlib_parse_snapinfo(launchpad, arg.lpurl)
        # If the previous build failed it needs manual review and isn't going to be retried
        if True:# not snapinfo or snapinfo[buildarch][0] == 'B':
            print("Rebuilding the snap on %s" % buildarch)
            buildserie = arg.serie
            if 'serie' in snapinfo:
                buildserie = snapinfo['serie']
                print("Build serie %s" % buildserie)
            cmd = ["lp-build-snap", "--lpname", snapinfo['owner'], "--arch", buildarch, "--series", buildserie, snapinfo['name']]
            print(cmd)
            if buildarch == 'armhf':
                subprocess.run(cmd, check=True)
        else:
            print("Outdated on %s but the previous build failed or is missing so we are not retrying automatically" % buildarch)
    else:
        print("Snap doesn't needs a rebuild on %s" % buildarch)

print("")
