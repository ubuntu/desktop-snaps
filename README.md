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

This tool can also be used to automate version updates of snap based on a specified version schema.
When the `--version-schema` (optional) flag is provided as input, the tool will automatically increment the version according to the specified schema.

To include this feature as a github worflow you need to pass an optional input in `with` command.

### How Snap Version Automation Works

The snap version automation feature functions by extracting version information from the designated section labeled as `adopt-info`. Subsequently, it automatically updates the version of the primary snap. This versioning scheme consists of two components:

- **Primary Upstream Component Version**: This component comprises the version number of the primary upstream component, which is extracted from the `adopt-info` section.

- **Package Release Number**: The package release number is represented by a small integer and indicates the number of releases of the snap, provided the primary upstream component remains unchanged. In case of a new release of the primary component, the version number is incremented accordingly, with the package release number being reset to 1. Additionally, any other modifications to the package result in an increment of the package release number by 1.

**Example:**
For `cups-snap`, the version is defined as `2.4.7-6`, where `2.4.7` represents the primary upstream component source tag derived from part of the `adopt info` section, and `6` signifies the package release.

**Prerequisites to Apply Snap Version Automation:**
Before applying snap version automation, ensure the following prerequisites are met:

- The `version` must be explicitly defined in the snapcraft.yaml metadata, preferably in the headers section of the respective project.
- The `adopt-info` section must be included in snapcraft.yaml metadata to ensure that the primary upstream component can be derived from it.
- Correct definition of the `version-schema` in the GitHub workflow is essential for smooth operation.

***Examples of Version-Schema:***

| Source Tag of Primary Upstream Component | Version-Schema | Snap Version |
|----------|----------|----------|
| v2.4.7 | 'v(\d+\.\d+\.\d+)' | 2.4.7-2 |
| debian/3.22.10+dfsg0-4 | '^debian/(\d+\.\d+\.\d+)' | 3.22.10-5 |
| 20240108 | '^(\d{8})' | 20240108-1 |
| ghostpdl-10.02.1 | '^ghostpdl-(\d+\.\d+\.\d+)' | 10.02.1-6 |

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

For example, to use snap version automation
```
name: Push new tag update to stable branch

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
        uses: ubuntu/desktop-snaps@stable
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
          repo: ${{ github.repository }}
          version-schema: '^debian/(\d+\.\d+\.\d+)'
```
