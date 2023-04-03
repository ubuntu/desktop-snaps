#!/usr/bin/env python3

import sys
import os

base_file = sys.argv[1]
destination = os.path.join(sys.argv[2], base_file)

def load_module(name, path):
    global modules

    imports = []
    content = ""
    with open(path, "r") as ifile:
        for line in ifile:
            if line.startswith("import ") or line.startswith("from "):
                imports.append(line.strip())
                continue
            content += line
    modules[name] = {"imports": imports, "content": content}

def add_import(ip):
    global imports

    if ip in imports:
        return
    imports.append(ip)

modules = {}
load_module("SnapModule.snapmodule", "SnapModule/snapmodule.py")

imports = []

contents = ""

with open(base_file, "r") as ifile:
    for line in ifile:
        if line.strip() == "from SnapModule.snapmodule import Snapcraft":
            for ip in modules["SnapModule.snapmodule"]["imports"]:
                add_import(ip)
            contents += modules["SnapModule.snapmodule"]["content"]
            continue
        if line.strip() == "from SnapModule.snapmodule import Github":
            continue
        if line.startswith("import ") or (line.startswith("from ")):
            add_import(line.strip())
            continue

with open(destination, "w") as ofile:
    ofile.write("#!/usr/bin/env python3\n\n")
    for ip in imports:
        ofile.write(f"{ip}\n")
    ofile.write("\n")
    ofile.write(contents)
    ofile.write("\n")
    with open(base_file, "r") as ifile:
        for line in ifile:
            if line.strip().startswith("#"):
                continue
            if line.startswith("import ") or line.startswith("from "):
                continue
            ofile.write(line)

os.chmod(destination, 0o755 )
