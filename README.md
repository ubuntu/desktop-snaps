# Toolbox

This repository is a collection of automation tools needed for the snaps on Ubuntu desktop.

The tools should be able to automatically:
- notice when there is a new tag upstream vs what we have in the snap store --candidate
- open issue about new version
- open PR with new candidate version change (the PR will generate a build)
- launch newly built snap (possibly using xvfb) and grab a screenshot and attach it to the PR

Then when a project has a new upstream patch, all we need to review is the automatically opened PR and screenshot.
Once the PR has been manually merged, the launchpad mirror will pick up the change and automatically build a snap for --candidate.
Then the snap in --candidate needs to be manually tested before promoting it to --stable.


## Tools in the Toolbox

### candidate-snaps-review

This tool is really a set of 3 useful tools:
* _snapchanges.py_ is a utility to display changes in a snap between stable and candidate channels
* _snaps.py_ defines the list of snaps the Ubuntu Desktop team is interested in
* _candidate.yml_ is a cache of candidate revisions already processed
* _close-fixed-issues.py_ closes issues that were opened against a candidate no longer available

### updatesnap.py
This tool eases the inspection of the gnome-sdk snap that builds many parts. Since each part points to an upstream repo, updatesnap.py will check for newer upstream releases than the gnome-sdk part contains. It outputs an array of the update data.

This data should be included in any automatically created PR.

### updatesnapyaml.py
This tool utilizes updatesnap.py to generate a new snapcraft.yaml with the tag updated, provided a new tag is available upstream.

For example, to run it locally on another repo (gnome-calculator in this case) to generate the update, pass it the url of the repo with the snapcraft.yaml in quesiton to be updated:

```
./updatesnap/updatesnapyaml.py --github-user GITHUB_USER --github-token GITHUB_TOKEN https://github.com/ubuntu/gnome-calculator.git
```

### GitHub action
This action should be utilized by other repos' workflows. The action checks out this repository to use updatesnapyaml.py and replaces the old snapcraft.yaml with the new one.

For example, to use this directly in another repo's workflow:

```
name: Open a PR if a new update is available

on:
  schedule:
    # Daily for now
    - cron: '9 7 * * *'
  workflow_dispatch:

jobs:
  update-snapcraft-yaml:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout this repo
        uses: actions/checkout@v3
      - name: Run desktop-snaps action
        uses: ubuntu/desktop-snaps@add-action
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
          repo: ${{ github.repository }}
```
