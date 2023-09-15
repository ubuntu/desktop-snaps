#!/usr/bin/python3
"""Notify about snaps candidate updates and provide details for review"""
import argparse
import json
import os
import subprocess
import urllib.request

import yaml

import snaps

# use existing cache
try:
    with open("candidate.yml", "r") as candidatereport:
        candidatedict = yaml.load(candidatereport, Loader=yaml.Loader)
except FileNotFoundError:
    candidatedict = {}

parser = argparse.ArgumentParser()

parser.add_argument(
    "-v", "--verbose", help="display debug information", action="store_true"
)

arg = parser.parse_args()


def debug(text):
    """ Print when using the verbose option"""
    if arg.verbose:
        print(text)


STORE_URL = "https://api.snapcraft.io/api/v1/snaps/details/{snap}?channel={channel}"
STORE_HEADERS = {"X-Ubuntu-Series": "16", "X-Ubuntu-Architecture": "{arch}"}
CHECK_NOTICES_PATH = "/snap/bin/review-tools.check-notices"


def store_parse_versions(package):
    """Build a dictionnary of the channels and revisions of a snap in the store"""
    result = {}
    # the store wants a Snap-Device-Series header
    req = urllib.request.Request(
        "http://api.snapcraft.io/v2/snaps/info/%s" % package,
        headers={"Content-Type": "application/json", "Snap-Device-Series": "16"},
    )
    snapdetails = urllib.request.urlopen(req)

    store = json.load(snapdetails)
    for items in store["channel-map"]:
        larch = items["channel"]["architecture"]
        lchannel = items["channel"]["name"]
        lrev = items["revision"]
        if larch not in result:
            result[larch] = {}
        result[larch][lchannel] = lrev
    return result


if not os.path.isdir("reports"):
    os.mkdir("reports")

# iterate over the list of snaps
for snapline in snaps.normalsnaps + snaps.specialsnaps:
    oldchan = "stable"
    newchan = "candidate"

    track = "/" + snapline[8] if snapline[8] else ""

    store_revisions = set()
    revisions_to_delete = set()

    src = snapline[0]
    if not snapline[1]:
        debug("skip %s since there is no stable build" % src)

    debug("* considering source %s %s" % (src, "latest" if track == "" else track[0:-1]))
    if track + src not in candidatedict:
        candidatedict[track + src] = []

    store_versions_table = store_parse_versions(src)
    debug("store versions")
    debug(store_versions_table)

    for architecture in store_versions_table:
        if architecture != "amd64":
            debug("Limiting to amd64 for now")
            continue

        if track + oldchan not in store_versions_table[architecture].keys():
            debug("Ignoring since there is no version in %s" % track + oldchan)
            continue

        for channel in store_versions_table[architecture]:
            if channel != track + newchan:
                continue

            rev = store_versions_table[architecture][channel]
            store_revisions.add(rev)

            if rev == store_versions_table[architecture][track + oldchan]:
                debug("The new channel revision is identic, nothing to do")
                if rev in candidatedict[track + src]:
                    revisions_to_delete.add(rev)
                continue

            if rev in candidatedict[track + src]:
                debug("rev %s has already been handled" % rev)
                continue

            changes = subprocess.check_output(
                ["./snapchanges.py", oldchan, newchan, src, "latest" if track == "" else track[0:-1] ], encoding="UTF-8"
            )

            report = {}
            report["title"] = "New %scandidate build available for %s on %s (r%s)" % (
                track,
                src,
                architecture,
                rev,
            )
            report["body"] = (
                "Reported changes between the current stable and the new candidate\n\n```\n"
                + changes[:61000]
                + "```\n"
            )

            if len(changes) > 61000:
                report["body"] += "<WARNING: The content of the report has been truncated to respect the github API limitations>"

            with open(
                "reports/%s-%s-%s.json" % (src, architecture, rev), "w"
            ) as reportfile:
                json.dump(report, reportfile)
            candidatedict[track + src].append(rev)

    for rev in candidatedict[track + src]:
        if rev not in store_revisions:
            debug("Remove %s rev %s which isn't in the store anymore" % (track + src, rev))
            revisions_to_delete.add(rev)
    for rev in revisions_to_delete:
        debug("Cleaning out outdated revision %s from the cache" % rev)
        candidatedict[track + src].remove(rev)
    debug("")

# write updated cache
with open("candidate.yml", "w") as outfile:
    yaml.dump(candidatedict, outfile, default_flow_style=False)
