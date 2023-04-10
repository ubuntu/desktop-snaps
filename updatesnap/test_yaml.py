#!/usr/bin/env python3

import unittest
import os
import datetime
from SnapModule.snapmodule import Snapcraft
from SnapModule.snapmodule import ManageYAML

class GitPose(object):
  def __init__(self):
    self._tags = {}
    self._branches = {}

  def set_secrets(self, data):
    pass

  def set_tags(self, tags):
    self._tags = tags

  def set_branches(self, branches):
    self._branches = branches

  def get_tags(self, source, current_tag = None, version_format = {}):
    if source in self._tags:
      return self._tags[source]
    else:
      return []


class TestYAMLfiles(unittest.TestCase):

  def _load_test_file(self, filepath, tags = {}):
    with open(os.path.join("tests", filepath), "r") as datafile:
      data = datafile.read()
    while data[:-2] == "\n\n":
      data = data[:-1]

    github_pose = GitPose()
    github_pose.set_tags(tags)
    gitlab_pose = GitPose()
    gitlab_pose.set_tags(tags)
    snap = Snapcraft(True, github_pose, gitlab_pose)
    snap.load_external_data(data)
    return snap, data


  def _ensure_tags(self, data, tags):
    tagdict = {}
    for tag in tags:
      tagdict[tag] = False
    for element in data:
      if element["name"] not in tagdict:
        return False
      tagdict[element["name"]] = True
    for tag in tagdict:
      if not tagdict[tag]:
        return False
    return True


  def _get_gnome_calculator_tags(self):
    return {"https://gitlab.gnome.org/GNOME/gnome-calculator.git":
            [
              {'name': '44.0', 'date': datetime.datetime(2023, 3, 17, 22, 17, 18, tzinfo=datetime.timezone(datetime.timedelta(seconds=7200)))},
              {'name': '44.rc', 'date': datetime.datetime(2023, 3, 3, 22, 33, 23, tzinfo=datetime.timezone(datetime.timedelta(seconds=7200)))},
              {'name': '44.beta', 'date': datetime.datetime(2023, 2, 11, 21, 31, 11, tzinfo=datetime.timezone(datetime.timedelta(seconds=7200)))},
              {'name': '43.0.1', 'date': datetime.datetime(2022, 9, 16, 20, 40, 1, tzinfo=datetime.timezone(datetime.timedelta(seconds=10800)))},
              {'name': '43.0', 'date': datetime.datetime(2022, 9, 16, 19, 58, 24, tzinfo=datetime.timezone(datetime.timedelta(seconds=10800)))},
              {'name': '43.rc', 'date': datetime.datetime(2022, 9, 2, 23, 14, 40, tzinfo=datetime.timezone(datetime.timedelta(seconds=10800)))},
              {'name': '43.alpha', 'date': datetime.datetime(2022, 7, 8, 16, 48, 43, tzinfo=datetime.timezone(datetime.timedelta(seconds=10800)))},
              {'name': '42.2', 'date': datetime.datetime(2022, 7, 1, 23, 15, 12, tzinfo=datetime.timezone(datetime.timedelta(seconds=10800)))},
              {'name': '42.1', 'date': datetime.datetime(2022, 5, 27, 19, 27, 52, tzinfo=datetime.timezone(datetime.timedelta(seconds=10800)))},
              {'name': '42.0', 'date': datetime.datetime(2022, 3, 19, 22, 15, 55, tzinfo=datetime.timezone(datetime.timedelta(seconds=7200)))},
              {'name': '42.rc', 'date': datetime.datetime(2022, 3, 6, 8, 15, 44, tzinfo=datetime.timezone(datetime.timedelta(seconds=7200)))},
              {'name': '42.beta', 'date': datetime.datetime(2022, 2, 13, 22, 0, 5, tzinfo=datetime.timezone(datetime.timedelta(seconds=7200)))},
              {'name': '42.alpha', 'date': datetime.datetime(2022, 1, 8, 23, 22, 56, tzinfo=datetime.timezone(datetime.timedelta(seconds=7200)))},
              {'name': '41.1', 'date': datetime.datetime(2021, 12, 6, 8, 47, 24, tzinfo=datetime.timezone(datetime.timedelta(seconds=7200)))},
              {'name': '41.0', 'date': datetime.datetime(2021, 9, 18, 22, 40, 23, tzinfo=datetime.timezone(datetime.timedelta(seconds=10800)))},
              {'name': '41.rc', 'date': datetime.datetime(2021, 9, 4, 20, 28, 37, tzinfo=datetime.timezone(datetime.timedelta(seconds=10800)))},
              {'name': '41.alpha', 'date': datetime.datetime(2021, 7, 10, 8, 44, 20, tzinfo=datetime.timezone(datetime.timedelta(seconds=10800)))},
              {'name': '40.1', 'date': datetime.datetime(2021, 4, 30, 16, 38, 38, tzinfo=datetime.timezone(datetime.timedelta(seconds=10800)))},
              {'name': '40.0', 'date': datetime.datetime(2021, 3, 19, 20, 32, 6, tzinfo=datetime.timezone(datetime.timedelta(seconds=7200)))},
              {'name': '40.rc', 'date': datetime.datetime(2021, 3, 12, 19, 32, 25, tzinfo=datetime.timezone(datetime.timedelta(seconds=7200)))}
            ]
          }

  def test_gnome_calculator_1(self):
    # tests if it detects the right list of available updates
    snap, datafile = self._load_test_file("gnome-calculator-test1.yaml", self._get_gnome_calculator_tags())
    data = snap.process_parts()
    assert self._ensure_tags(data[0]["updates"], ["44.0", "43.0.1", "43.0"])
    assert not self._ensure_tags(data[0]["updates"], ["44.0", "43.0.1", "43.0", "42.2"])

  def test_gnome_calculator_2(self):
    # tests if the updated snapcraft.yaml file is correct
    snap, datafile = self._load_test_file("gnome-calculator-test1.yaml", self._get_gnome_calculator_tags())
    data = snap.process_parts()
    managerYAML = ManageYAML(datafile)
    has_update = False
    for part in data:
      if not part:
        continue
      if not part['updates']:
        continue
      version_data = managerYAML.get_part_element(part['name'], 'source-tag:')
      if not version_data:
        continue
      #print(f"Updating '{part['name']}' from version '{part['version'][0]}' to version '{part['updates'][0]['name']}'")
      version_data['data'] = f"source-tag: '{part['updates'][0]['name']}'"
      has_update = True
    version_data = managerYAML.get_part_element("gnome-calculator", 'source-tag:')
    assert version_data['data'] == "source-tag: '44.0'"
    assert (managerYAML.get_yaml() == """name: gnome-calculator
adopt-info: gnome-calculator
summary: GNOME Calculator
description: |
  GNOME Calculator is an application that solves mathematical equations.
  Though it at first appears to be a simple calculator with only basic
  arithmetic operations, you can switch into Advanced, Financial, or
  Programming mode to find a surprising set of capabilities.

  The Advanced calculator supports many operations, including:
  logarithms, factorials, trigonometric and hyperbolic functions,
  modulus division, complex numbers, random number generation, prime
  factorization and unit conversions.

  Financial mode supports several computations, including periodic interest
  rate, present and future value, double declining and straight line
  depreciation, and many others.

  Programming mode supports conversion between common bases (binary, octal,
  decimal, and hexadecimal), boolean algebra, one’s and two’s complementation,
  character to character code conversion, and more.

grade: stable # must be 'stable' to release into candidate/stable channels
confinement: strict
base: core22

slots:
  # for GtkApplication registration
  gnome-calculator:
    interface: dbus
    bus: session
    name: org.gnome.Calculator

apps:
  gnome-calculator:
    command: usr/bin/gnome-calculator
    extensions: [gnome]
    plugs:
      - gsettings
      - network
      - network-status
    desktop: usr/share/applications/org.gnome.Calculator.desktop
    common-id: org.gnome.Calculator.desktop

parts:
  gnome-calculator:
    source: https://gitlab.gnome.org/GNOME/gnome-calculator.git
    source-tag: '44.0'
# ext:updatesnap
#   version-format:
#     no-9x-revisions: true
    plugin: meson
    parse-info: [usr/share/metainfo/org.gnome.Calculator.appdata.xml]
    meson-parameters:
      - --prefix=/snap/gnome-calculator/current/usr
      - --buildtype=release
      - -Dvala_args="--vapidir=$CRAFT_STAGE/usr/share/vala/vapi"
      - -Ddisable-introspection=true
    organize:
      snap/gnome-calculator/current/usr: usr
    build-packages:
      - libmpc-dev
      - libmpfr-dev
      - libgvc6
    override-pull: |
      craftctl default
      craftctl set version=$(git describe --tags --abbrev=10)
    override-build: |
      # valadoc fails, but we don't need it in the snap anyway
      sed -i.bak -e "s|subdir('doc')||g" $CRAFT_PART_SRC/meson.build
      # Don't symlink media it leaves dangling symlinks in the snap
      sed -i.bak -e 's|media: gnome_calculator_help_media|media: gnome_calculator_help_media, symlink_media: false|g' $CRAFT_PART_SRC/help/meson.build
      # Use bundled icon rather than themed icon, needed for 18.04
      sed -i.bak -e 's|Icon=org.gnome.Calculator$|Icon=${SNAP}/meta/gui/org.gnome.Calculator.svg|g' $CRAFT_PART_SRC/data/org.gnome.Calculator.desktop.in
      mkdir -p $CRAFT_PART_INSTALL/meta/gui/
      cp $CRAFT_PART_SRC/data/icons/hicolor/scalable/apps/org.gnome.Calculator.svg $CRAFT_PART_INSTALL/meta/gui/
      craftctl default

  # Find files provided by the base and platform snap and ensure they aren't
  # duplicated in this snap
  cleanup:
    after: [gnome-calculator]
    plugin: nil
    build-snaps: [core22, gtk-common-themes, gnome-42-2204]
    override-prime: |
      set -eux
      for snap in "core22" "gtk-common-themes" "gnome-42-2204"; do
        cd "/snap/$snap/current" && find . -type f,l -name *.so.* -exec rm -f "$CRAFT_PRIME/{}" \\;
      done
""")


  def test_gnome_calculator_3(self):
    snap, datafile = self._load_test_file("gnome-calculator-test1.yaml", self._get_gnome_calculator_tags())
    data = snap.process_parts()
    managerYAML = ManageYAML(datafile)
    assert managerYAML.get_yaml() == datafile


unittest.main()
