#!/usr/bin/env python3

""" Unitary tests for snapmodule """

import unittest
import os
import datetime
from SnapModule.snapmodule import Snapcraft
from SnapModule.snapmodule import ManageYAML
from SnapModule.snapmodule import ProcessVersion

class TestYAMLfiles(unittest.TestCase):
    """ Unitary tests for snapmodule """

    def _load_test_file(self, filepath, tags):
        with open(os.path.join("tests", filepath), "r", encoding='utf-8') as datafile:
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
        for tag in tagdict.items():
            if not tag[1]:
                return False
        return True

    def test_gnome_calculator_1(self):
        """ tests if it detects the right list of available updates """
        snap, _ = self._load_test_file("gnome-calculator-test1.yaml",
                                              get_gnome_calculator_tags())
        data = snap.process_parts()
        assert self._ensure_tags(data[0]["updates"], ["44.0", "43.0.1", "43.0"])
        assert not self._ensure_tags(data[0]["updates"], ["44.0", "43.0.1", "43.0", "42.2"])


    def test_gnome_calculator_2(self):
        """ tests if the updated snapcraft.yaml file is correct """
        snap, datafile = self._load_test_file("gnome-calculator-test1.yaml",
                                              get_gnome_calculator_tags())
        data = snap.process_parts()
        manager_yaml = ManageYAML(datafile)
        has_update = False
        for part in data:
            if not part:
                continue
            if not part['updates']:
                continue
            version_data = manager_yaml.get_part_element(part['name'], 'source-tag:')
            if not version_data:
                continue
            version_data['data'] = f"source-tag: '{part['updates'][0]['name']}'"
            has_update = True
        version_data = manager_yaml.get_part_element("gnome-calculator", 'source-tag:')
        assert has_update
        assert version_data['data'] == "source-tag: '44.0'"
        assert remove_trailing_nls(manager_yaml.get_yaml()) == get_updated_yaml()


    def test_gnome_calculator_3(self):
        """ updates a YAML file and checks if the resulting YAML is correct """
        snap, datafile = self._load_test_file("gnome-calculator-test1.yaml",
                                              get_gnome_calculator_tags())
        data = snap.process_parts()
        assert len(data) == 2
        assert "name" in data[0]
        assert "version" in data[0]
        assert "updates" in data[0]
        assert data[0]["name"] == 'gnome-calculator'
        assert data[0]["version"][0] == '42.2'
        assert len(data[0]["updates"]) == 3
        assert data[0]["updates"][0]["name"] == "44.0"
        assert data[0]["updates"][1]["name"] == "43.0.1"
        assert data[0]["updates"][2]["name"] == "43.0"
        manager_yaml = ManageYAML(datafile)
        assert manager_yaml.get_yaml() == datafile

    def test_no_9x_revisions(self):
        obj = ProcessVersion(silent=True)
        entry_format = {"format":"%M.%m.%R", "no-9x-revisions": True}
        version = obj._get_version("testpart", "3.8.92", entry_format, False)
        assert version is None
        version = obj._get_version("testpart", "3.8.32", entry_format, False)
        assert str(version) == "3.8.32"

    def test_no_9x_minors(self):
        obj = ProcessVersion(silent=True)
        entry_format = {"format":"%M.%m.%R", "no-9x-minors": True}
        version = obj._get_version("testpart", "3.97.1", entry_format, False)
        assert version is None
        version = obj._get_version("testpart", "3.45.1", entry_format, False)
        assert str(version) == "3.45.1"


    def test_ignore_odd_minor(self):
        # pylint: disable=protected-access
        """ Tests the "ignore-odd-minor" option when parsing versions """
        obj = ProcessVersion(silent=True)
        entry_format = {"format":"%M.%m.%R", "ignore-odd-minor": True}
        version = obj._get_version("testpart", "2.43.6", entry_format, False)
        assert version is None
        version = obj._get_version("testpart", "3.42.1", entry_format, False)
        assert str(version) == "3.42.1"


class GitPose:
    """ Helper class. It emulates a GitClass class, to allow to test
        classes that depend on it, without having to rely on an external
        github or gitlab repository """
    def __init__(self):
        self._tags = {}
        self._branches = {}

    def set_secrets(self, data):
        """ emulates the set_secrets() method. """

    def set_tags(self, tags):
        """ Sets the tags that will be returned by this object when asked """
        self._tags = tags

    def set_branches(self, branches):
        """ Sets the bramches that will be returned by this object when asked """
        self._branches = branches

    def get_tags(self, source, current_tag = None, version_format = None):
        # pylint: disable=unused-argument
        """ Implements the get_tags() method of GitClass """
        if source in self._tags:
            return self._tags[source]
        return []


def get_gnome_calculator_tags():
    """ Returns a plausible list of tags for several tests """
    return {"https://gitlab.gnome.org/GNOME/gnome-calculator.git":
        [
            {'name': '44.0', 'date': datetime.datetime(2023, 3, 17, 22, 17, 18,
                    tzinfo=datetime.timezone(datetime.timedelta(seconds=7200)))},
            {'name': '44.rc', 'date': datetime.datetime(2023, 3, 3, 22, 33, 23,
                    tzinfo=datetime.timezone(datetime.timedelta(seconds=7200)))},
            {'name': '44.beta', 'date': datetime.datetime(2023, 2, 11, 21, 31, 11,
                    tzinfo=datetime.timezone(datetime.timedelta(seconds=7200)))},
            {'name': '43.0.1', 'date': datetime.datetime(2022, 9, 16, 20, 40, 1,
                    tzinfo=datetime.timezone(datetime.timedelta(seconds=10800)))},
            {'name': '43.0', 'date': datetime.datetime(2022, 9, 16, 19, 58, 24,
                    tzinfo=datetime.timezone(datetime.timedelta(seconds=10800)))},
            {'name': '43.rc', 'date': datetime.datetime(2022, 9, 2, 23, 14, 40,
                    tzinfo=datetime.timezone(datetime.timedelta(seconds=10800)))},
            {'name': '43.alpha', 'date': datetime.datetime(2022, 7, 8, 16, 48, 43,
                    tzinfo=datetime.timezone(datetime.timedelta(seconds=10800)))},
            {'name': '42.2', 'date': datetime.datetime(2022, 7, 1, 23, 15, 12,
                    tzinfo=datetime.timezone(datetime.timedelta(seconds=10800)))},
            {'name': '42.1', 'date': datetime.datetime(2022, 5, 27, 19, 27, 52,
                    tzinfo=datetime.timezone(datetime.timedelta(seconds=10800)))},
            {'name': '42.0', 'date': datetime.datetime(2022, 3, 19, 22, 15, 55,
                    tzinfo=datetime.timezone(datetime.timedelta(seconds=7200)))},
            {'name': '42.rc', 'date': datetime.datetime(2022, 3, 6, 8, 15, 44,
                    tzinfo=datetime.timezone(datetime.timedelta(seconds=7200)))},
            {'name': '42.beta', 'date': datetime.datetime(2022, 2, 13, 22, 0, 5,
                    tzinfo=datetime.timezone(datetime.timedelta(seconds=7200)))},
            {'name': '42.alpha', 'date': datetime.datetime(2022, 1, 8, 23, 22, 56,
                    tzinfo=datetime.timezone(datetime.timedelta(seconds=7200)))},
            {'name': '41.1', 'date': datetime.datetime(2021, 12, 6, 8, 47, 24,
                    tzinfo=datetime.timezone(datetime.timedelta(seconds=7200)))},
            {'name': '41.0', 'date': datetime.datetime(2021, 9, 18, 22, 40, 23,
                    tzinfo=datetime.timezone(datetime.timedelta(seconds=10800)))},
            {'name': '41.rc', 'date': datetime.datetime(2021, 9, 4, 20, 28, 37,
                    tzinfo=datetime.timezone(datetime.timedelta(seconds=10800)))},
            {'name': '41.alpha', 'date': datetime.datetime(2021, 7, 10, 8, 44, 20,
                    tzinfo=datetime.timezone(datetime.timedelta(seconds=10800)))},
            {'name': '40.1', 'date': datetime.datetime(2021, 4, 30, 16, 38, 38,
                    tzinfo=datetime.timezone(datetime.timedelta(seconds=10800)))},
            {'name': '40.0', 'date': datetime.datetime(2021, 3, 19, 20, 32, 6,
                    tzinfo=datetime.timezone(datetime.timedelta(seconds=7200)))},
            {'name': '40.rc', 'date': datetime.datetime(2021, 3, 12, 19, 32, 25,
                    tzinfo=datetime.timezone(datetime.timedelta(seconds=7200)))}
        ]
    }


def get_updated_yaml():
    """ Returns the updated yaml for gnome-calculator-test1 """
    with open("tests/gnome-calculator-test1-updated.yaml", "r", encoding="utf-8") as yaml_file:
        data = yaml_file.read()
    return remove_trailing_nls(data)

def remove_trailing_nls(data):
    """ removes all the trailing empty lines in a string """
    while data[-1] == '\n':
        data = data[:-1]
    return data

unittest.main()
