## Toolbox

This repository is a collection of automation tools needed for the snaps on Ubuntu desktop.

The tools should be able to automatically:
- notice when there is a new tag upstream vs what we have in the snap store --candidate
- open issue about new version
- open PR with new candidate version change (the PR will generate a build)
- launch newly built snap (possibly using xvfb) and grab a screenshot and attach it to the PR

Then when a project has a new upstream patch, all we need to review is the automatically opened PR and screenshot.
Once the PR has been manually merged, the launchpad mirror will pick up the change and automatically build a snap for --candidate.
Then the snap in --candidate needs to be manually tested before promoting it to --stable.
