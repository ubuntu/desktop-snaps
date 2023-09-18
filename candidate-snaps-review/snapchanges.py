#!/usr/bin/python3
"""Script to show the changes between snaps in channels"""
import argparse
import filecmp
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request

# handle cmdline arguments
parser = argparse.ArgumentParser()
parser.add_argument("channelold")
parser.add_argument("channelnew")
parser.add_argument("source")
parser.add_argument("track")
parser.add_argument(
    "-a",
    "--arch",
    help="on which architecture",
    default="amd64",
)
parser.add_argument(
    "-c",
    "--clean",
    help="clean the cache",
    action="store_true",
)
parser.add_argument(
    "-d",
    "--detail",
    help="display the details",
    action="store_true",
)
parser.add_argument(
    "-v", "--verbose", help="display debug information", action="store_true"
)
arg = parser.parse_args()

def get_snap_rev(snap, arch, channel, track):
    """Get the revision of a snap by name/arch/track/channel"""
    url = (
        f"https://api.snapcraft.io/v2/snaps/info/{snap}?architecture={arch}"
    )
    store = {"Snap-Device-Series": "16"}
    req = urllib.request.Request(
        url,
        headers=store
    )
    snapdetails = urllib.request.urlopen(req)
    channelmap = json.load(snapdetails)["channel-map"]
    return [item["revision"] for item in channelmap if (item["channel"]["risk"] == channel and item["channel"]["track"] == track)][0]


REDCOLOR = "\033[91m"
YELLOWCOLOR = "\033[93m"


def debug(text):
    """Print when using the verbose option."""
    if arg.verbose:
        print(text)


def sizeof_fmt(num, suffix="B"):
    """Print with the right units"""
    for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f} {unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f} Yi{suffix}"


def print_diff_files(dcmp):
    """Build lists of the changes"""
    for name in dcmp.diff_files:
        # ignore snapcraft artifacts
        if name in ["snap.yaml", "manifest.yaml", "snapcraft.yaml"]:
            continue
        set_changed.add(dcmp.left.replace(old_snap_dir, "") + "/" + name)
    if dcmp.left_only:
        for filename in dcmp.left_only:
            set_removed.add(dcmp.left.replace(old_snap_dir, "") + "/" + filename)
    if dcmp.right_only:
        for filename in dcmp.right_only:
            set_added.add(dcmp.right.replace(new_snap_dir, "") + "/" + filename)
    for sub_dcmp in dcmp.subdirs.values():
        print_diff_files(sub_dcmp)


def clean_dot_symlink(directory):
    """Workaround directory pointing to ."""
    for subdir, dirs, files in os.walk(directory):
        for drt in dirs:
            if os.path.islink(os.path.join(subdir, drt)):
                if os.readlink(os.path.join(subdir, drt)) == ".":
                    print("remove . symlink", os.path.join(subdir, drt))
                    os.remove(os.path.join(subdir, drt))


if arg.clean and os.path.exists("cache"):
    print("cleaning the cache")
    shutil.rmtree("cache")

# Get the revisions
oldrev = get_snap_rev(arg.source, arg.arch, arg.channelold, arg.track)
newrev = get_snap_rev(arg.source, arg.arch, arg.channelnew, arg.track)

if oldrev == newrev:
    print("The channels are on the same revision, nothing to compare")
    sys.exit(1)

# Define the cache directories to use
old_snap_dir = f"cache/{arg.source}-{oldrev}"
new_snap_dir = f"cache/{arg.source}-{newrev}"

# Define the request environment to select the arch for snap download
download_env = os.environ.copy()
download_env["UBUNTU_STORE_ARCH"] = arg.arch

arg.track = arg.track + "/"

# download the old snap from the corresponding channel
print(
    f"Downloading {arg.source} {arg.arch} from channel {arg.track}{arg.channelold} (r{oldrev}) to cache directory"
)
cmd = [
    "snap",
    "download",
    "--channel=%s%s" % (arg.track, arg.channelold),
    "--target-directory=cache/",
    arg.source,
]
output = subprocess.run(cmd, check=True, capture_output=True, env=download_env)

# unpack
if not os.path.exists(old_snap_dir):
    print("Unpackaging")
    cmd = ["unsquashfs", "-d", old_snap_dir, f"cache/{arg.source}_{oldrev}.snap"]
    output = subprocess.run(cmd, check=True, capture_output=True)
    clean_dot_symlink(old_snap_dir)
else:
    debug("The target cache directory exists, doing nothing")

# download the new snap from the corresponding channel
print(
    f"Downloading {arg.source} {arg.arch} from channel {arg.track}{arg.channelnew} (r{newrev}) to cache directory"
)
cmd = [
    "snap",
    "download",
    "--channel=%s%s" % (arg.track, arg.channelnew),
    "--target-directory=cache/",
    arg.source,
]
output = subprocess.run(cmd, check=True, capture_output=True, env=download_env)

# unpack
if not os.path.exists(new_snap_dir):
    print("Unpackaging")
    cmd = ["unsquashfs", "-d", new_snap_dir, f"cache/{arg.source}_{newrev}.snap"]
    output = subprocess.run(cmd, check=True, capture_output=True)
    clean_dot_symlink(new_snap_dir)
else:
    debug("The target cache directory exists, doing nothing")
print("")

print("Changes to the snap manifest")
cmd = [
    "diff",
    "-u",
    "--color",
    old_snap_dir + "/snap/manifest.yaml",
    new_snap_dir + "/snap/manifest.yaml",
]
output = subprocess.run(cmd)
print("")

old_snap_dsk = os.path.getsize(f"cache/{arg.source}_{oldrev}.snap")
new_snap_dsk = os.path.getsize(f"cache/{arg.source}_{newrev}.snap")
print("Size of the old snap:", sizeof_fmt(old_snap_dsk))
print("Size of the new snap:", sizeof_fmt(new_snap_dsk))
print("")
snap_dsk_delta = (new_snap_dsk - old_snap_dsk) / old_snap_dsk * 100

set_changed = set()
set_removed = set()
set_added = set()

DirCompare = filecmp.dircmp(old_snap_dir, new_snap_dir)
print_diff_files(DirCompare)

lst_changed = sorted(list(set_changed))
lst_removed = sorted(list(set_removed))
lst_added = sorted(list(set_added))

if lst_changed:
    if len(lst_changed) > 10 and not arg.detail:
        print(
            "Number of files changed (use -d to have the details)\n%s"
            % len(lst_changed)
        )
    else:
        print("Files changed")
        for f in lst_changed:
            print(f" {f}")
else:
    print("No file changed")
print("")

if lst_removed:
    if len(lst_removed) > 10 and not arg.detail:
        print(
            "Number of files removed (use -d to have the details)\n%s"
            % len(lst_removed)
        )
    else:
        print("Files removed")
        for f in lst_removed:
            print(f" {f}")
else:
    print("No file removed")
print("")

if lst_added:
    if len(lst_added) > 10 and not arg.detail:
        print("Number of files added (use -d to have the details)\n%s" % len(lst_added))
    else:
        print("Files added")
        for f in lst_added:
            print(f" {f}")
else:
    print("No file added")
print("")

str_warning = ""

if abs(snap_dsk_delta) >= 10:
    if snap_dsk_delta >= 0:
        str_warning += (
            REDCOLOR + "Warning, the diskspace increased by %0d%%\n" % snap_dsk_delta
        )
    else:
        str_warning += REDCOLOR + "Warning, the diskspace decreased by %0d%%\n" % abs(
            snap_dsk_delta
        )
    str_warning += "\n"

for file in lst_removed:
    if re.match(r".*(lib.*\.so\.\d+)$", file):
        str_warning += (
            REDCOLOR + file + " was removed which seems like a shared library\n"
        )

for file in lst_added:
    if re.match(r".*(lib.*\.so\.\d+)$", file):
        str_warning += (
            YELLOWCOLOR + file + " was added which seems like a shared library\n"
        )

if str_warning:
    print(
        "\n--------------------------------------\nYou might want to verify those points!\n--------------------------------------\n"
    )
    print(str_warning)
