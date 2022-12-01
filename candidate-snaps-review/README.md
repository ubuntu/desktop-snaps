# candidate-snaps-review

## Description

Experiment to facilitate the review of candidate snaps that need promotion to stable. The script iterates over the desktop snaps checking for those having a new revision available in candidate, calls one of our script built to show changes between channels and attach the output to a new issue.

## Notes

* _snapchanges.py_ is an utility to display changes in a snap between channels, it is hosted at https://code.launchpad.net/~ubuntu-desktop/+git/scriptish. A copy is included there to avoid having to do a checkout for every job
* _snaps.py_ is a hacked copy of the source hosted at https://code.launchpad.net/ubuntu-desktop-versions/+git which defines the list of snaps the Ubuntu Desktop team is interested in
* _candidate.yml_ is a cache of candidate revision already processed
