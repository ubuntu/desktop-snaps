#!/usr/bin/python3
"""Close bugs about a candidate which isn't available anymore"""
import json
import re
import sys
import urllib.request
import yaml

# use existing cache
try:
    with open("candidate.yml", "r") as candidatereport:
        candidatedict = yaml.load(candidatereport, Loader=yaml.Loader)
except FileNotFoundError:
    sys.exit("No candidate.yml record")

if len(sys.argv) != 3:
    sys.exit("Syntax is %s <GITHUB_API_URL> <TOKEN>" % sys.argv[0])
    
req = urllib.request.Request(sys.argv[1])
issues = urllib.request.urlopen(req)
for entry in json.load(issues):
    title = entry["title"]
    regexp = re.compile(r"New (.*)candidate build available for (.*) on .*\(r(\d*)\).*")
    parsed = regexp.search(title)
    if parsed:
        track, source, rev = parsed.groups()
        if track + source not in candidatedict or int(rev) not in candidatedict[track + source]:
            n = entry["number"]
            close_data = {"state": "closed"}
            msg_data = {
                "body": "Closing the bug since the revision isn't in the candidate channel anymore"
            }
            headers = {
                "authorization": "Bearer %s" % sys.argv[2],
            }

            print("Closing issue %s since %s r%s isn't in %scandidate anymore" % (n, source, rev, track))

            req = urllib.request.Request(
                sys.argv[1]+f"/{n}/comments",
                method="POST",
                headers=headers,
                data=bytes(json.dumps(msg_data), encoding="utf-8"),
            )
            urllib.request.urlopen(req)
            req = urllib.request.Request(
                sys.argv[1]+f"/{n}",
                method="PATCH",
                headers=headers,
                data=bytes(json.dumps(close_data), encoding="utf-8"),
            )
            urllib.request.urlopen(req)
