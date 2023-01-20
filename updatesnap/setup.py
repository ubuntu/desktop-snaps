#!/usr/bin/env python3
from setuptools import setup

setup(
    name = "updatesnap",
    version = "0.2.0",
    install_requires = [
        'requests',
    ],
    packages = ['SnapModule'],
    scripts = ['updatesnap.py','updatesnapyaml.py']
)
