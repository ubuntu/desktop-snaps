#!/bin/sh

test_style () {
    echo Checking $1 with Pylint
    pylint $1
}

test_style updatesnap.py
test_style updatesnapyaml.py
test_style SnapModule/snapmodule.py
test_style unittests.py
