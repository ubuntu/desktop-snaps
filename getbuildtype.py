#!/usr/bin/python3
"""Determine the type of build used by a snap manifest"""
import argparse
import os
import sys

import yaml

parser = argparse.ArgumentParser()
parser.add_argument(
    "-d",
    "--directory",
    help="directory which contains the snapcraft.yaml",
    default="",
)
arg = parser.parse_args()

# Default to read snapcraft.yaml from the local directory
srcfile = "snapcraft.yaml"
if arg.directory:
    srcfile = os.path.join(arg.directory, "snapcraft.yaml")

try:
    with open(srcfile, "r") as snapcraft:
        yml = yaml.load(snapcraft, Loader=yaml.Loader)
except FileNotFoundError:
    sys.exit("There is no snapcraft.yaml at the specified location")

src = yml["name"]
if "parts" in yml and src in yml["parts"]:
    srcsection = yml["parts"][src]
    if not ("source-type" in srcsection and srcsection["source-type"] == "git"):
        sys.exit("Source types other than git are not handled")
    source = srcsection["source"]
    if "source-branch" in srcsection:
        print(
            "git-branch -b %s -v %s -n %s" % (srcsection["source-branch"], source, src)
        )
    elif "source-tag" in srcsection:
        print("git-tag %s %s %s" % (srcsection["source-tag"], source, src))
    else:
        sys.exit("The snap is not built from a tag or branch")
else:
    sys.exit("No %s part found in the snapcraft.yaml\n" % src)
