#!/usr/bin/python3

import json
import re
import sys
import urllib.request

import snaps

if(len(sys.argv) != 3):
    print("Usage: two arguments are required, the issues API url for the repo and the token used by the action.")
    print("./check-builds.py https://api.github.com/repos/${{ github.repository }}/issues ${{ secrets.GITHUB_TOKEN }}")
    sys.exit()

req = urllib.request.Request(sys.argv[1])
issues = json.load(urllib.request.urlopen(req))

def get_builds(launchpad_url):
    req = urllib.request.Request(launchpad_url)
    builds_res = urllib.request.urlopen(req)

    builds = json.load(builds_res)
    arch = dict()
    i=0
    while(builds["entries"][i]["arch_tag"] not in arch):
        arch[builds["entries"][i]["arch_tag"]] = False if builds["entries"][i]["buildstate"] == "Failed to build" else True
        i+=1
    return arch

def open_issue(name, arch, url):            
    data = {
        "title": "%s build on %s is broken" % (name, arch),
        "body": "The last attempt to build %s on %s failed. Launchpad is reporting a \"Failed to build\" status. \n %s" % (name, arch, url),
        }
    headers = {
        "authorization": "Bearer %s" % sys.argv[2],
        }
    req = urllib.request.Request(
        sys.argv[1],
        method="POST",
        headers=headers,
        data=bytes(json.dumps(data), encoding="utf-8"),
    )
    urllib.request.urlopen(req)

def check_for_issues(name, arch):
    for entry in issues:
        title = entry["title"]
        regexp = re.compile(r"(.*) build on (.*) is broken")
        parsed = regexp.search(title)
        if parsed:
            issue_name, issue_arch = parsed.groups()
            if issue_name == name and issue_arch == arch:
              return entry["number"]
    return 0


def close_issue(n):            
    close_data = {"state": "closed"}
    headers = {
        "authorization": "Bearer %s" % sys.argv[2],
        }
    req = urllib.request.Request(
        sys.argv[1]+f"/{n}",
        method="PATCH",
        headers=headers,
        data=bytes(json.dumps(close_data), encoding="utf-8"),
    )
    urllib.request.urlopen(req)
      
# iterate over the list of snaps
for snapline in snaps.normalsnaps + snaps.specialsnaps:
    name = snapline[0]
    url = snapline[1]
    track = snapline[8]
    if(url != None):
        response = get_builds(url.replace("launchpad.net", "api.launchpad.net/1.0")+"/builds")
        for arch, result in response.items():
            # if the snap entry is tracking a specific channel, prepend it
            if track:
                issue = check_for_issues(track+"/"+name, arch)
            else:
                issue = check_for_issues(name, arch)
            if issue != 0 and result:
                close_issue(issue)
            elif issue == 0 and not result:
                # if the snap entry is tracking a specific channel, prepend it
                if track:
                    open_issue(track+"/"+name, arch, url)
                else:
                    open_issue(name, arch, url)
