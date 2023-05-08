#!/bin/sh

test_style () {
    echo Checking $1 with Pylint
    pylint $1
}

test_style abi_breaker.py
test_style unittests.py
