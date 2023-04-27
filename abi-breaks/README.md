# ABI break checker

This program compares the libraries inside two versions of the same SNAP to
ensure that there are no ABI breaks.

## Usage

Call *abi_breaker.py* with two paths, the first one pointing to the old
snap contents, and the second one pointing to the new snap contents.

Example: to compare the ABIs between the system-installed revisions 111
and 122 of gnome-42-2204-sdk:

    ./abi_breaker.py /snap/gnome-42-2204-sdk/111 /snap/gnome-42-2204-sdk/122
