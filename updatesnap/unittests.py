#!/usr/bin/env python3

""" Unitary tests for snapmodule """

import unittest
import os
import datetime
import sys
import yaml
from SnapModule.snapmodule import Snapcraft
from SnapModule.snapmodule import ManageYAML
from SnapModule.snapmodule import ProcessVersion
from SnapModule.snapmodule import Github
from SnapModule.snapmodule import Gitlab


class TestYAMLfiles(unittest.TestCase):
    # pylint: disable=too-many-public-methods
    """ Unitary tests for snapmodule """
    # pylint: disable=too-many-public-methods

    def _load_secrets(self, obj):
        secrets = None
        if "GITHUB_USER" in os.environ and "GITHUB_TOKEN" in os.environ:
            secrets = {"github": {"user": os.environ["GITHUB_USER"],
                       "token": os.environ["GITHUB_TOKEN"]}}
        elif len(sys.argv) >= 3:
            secrets = {"github": {"user": sys.argv[1], "token": sys.argv[2]}}
        else:
            secrets_file = os.path.expanduser('~/.config/updatesnap/updatesnap.secrets')
            if os.path.exists(secrets_file):
                with open(secrets_file, "r", encoding="utf8") as cfg:
                    secrets = yaml.safe_load(cfg)
        if secrets is not None:
            obj.set_secrets(secrets)

    def _base_load_test_file(self, filepath):
        with open(os.path.join("tests", filepath), "r", encoding='utf-8') as datafile:
            data = datafile.read()
        while data[:-2] == "\n\n":
            data = data[:-1]
        return data

    def _load_test_file(self, filepath, tags, branches=None):
        data = self._base_load_test_file(filepath)

        github_pose = GitPose()
        github_pose.set_tags(tags)
        github_pose.set_branches(branches)
        gitlab_pose = GitPose()
        gitlab_pose.set_tags(tags)
        gitlab_pose.set_branches(branches)
        snap = Snapcraft(True, github_pose, gitlab_pose)
        snap.set_full_silent()
        snap.load_external_data(data)
        return snap, data, github_pose, gitlab_pose

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
        snap, _, _, _ = self._load_test_file("gnome-calculator-test1.yaml",
                                             get_gnome_calculator_tags())
        data, tag_error = snap.process_parts()
        assert not tag_error
        assert self._ensure_tags(data[0]["updates"], ["44.0", "43.0.1", "43.0"])
        assert not self._ensure_tags(data[0]["updates"], ["44.0", "43.0.1", "43.0", "42.2"])

    def test_gnome_calculator_2(self):
        """ tests if the updated snapcraft.yaml file is correct """
        snap, datafile, _, _ = self._load_test_file("gnome-calculator-test1.yaml",
                                                    get_gnome_calculator_tags())
        data, tag_error = snap.process_parts()
        assert not tag_error
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
        """ Ensure that the updated file identical to the expected one """
        snap, datafile, _, _ = self._load_test_file("gnome-calculator-test1.yaml",
                                                    get_gnome_calculator_tags())
        data, tag_error = snap.process_parts()
        assert not tag_error
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
        # pylint: disable=protected-access
        """ Test the no-9x-revision option """
        obj = ProcessVersion(silent=True)
        obj.set_full_silent()
        entry_format = {"format": "%M.%m.%R", "no-9x-revisions": True}
        version = obj._get_version("testpart", "3.8.92", entry_format, False)
        assert version is None
        version = obj._get_version("testpart", "3.8.32", entry_format, False)
        assert str(version) == "3.8.32"

    def test_no_9x_minors(self):
        # pylint: disable=protected-access
        """ Test the no-9x-minors option """
        obj = ProcessVersion(silent=True)
        obj.set_full_silent()
        entry_format = {"format": "%M.%m.%R", "no-9x-minors": True}
        version = obj._get_version("testpart", "3.97.1", entry_format, False)
        assert version is None
        version = obj._get_version("testpart", "3.45.1", entry_format, False)
        assert str(version) == "3.45.1"

    def test_ignore_odd_minor(self):
        # pylint: disable=protected-access
        """ Tests the "ignore-odd-minor" option when parsing versions """
        obj = ProcessVersion(silent=True)
        obj.set_full_silent()
        entry_format = {"format": "%M.%m.%R", "ignore-odd-minor": True}
        version = obj._get_version("testpart", "2.43.6", entry_format, False)
        assert version is None
        version = obj._get_version("testpart", "3.42.1", entry_format, False)
        assert str(version) == "3.42.1"

    def test_github_file_download(self):
        """ Check that a file download from github works as expected """
        gitobj = Github(silent=True)
        gitobj.set_full_silent()
        self._load_secrets(gitobj)
        data = gitobj.get_file("https://github.com/ubuntu/gnome-calculator", "snapcraft.yaml")
        assert data is not None
        assert isinstance(data, bytes)
        content = data.decode('utf-8')
        assert isinstance(content, str)
        assert content.find('name: gnome-calculator') != -1

    def test_github_tags_download(self):
        """ Check that tag download from github works as expected """
        gitobj = Github(silent=True)
        gitobj.set_full_silent()
        self._load_secrets(gitobj)
        data = gitobj.get_tags("https://github.com/GNOME/gnome-calculator",
                               "40.0", {"format": "%M.%m"})
        assert isinstance(data, list)
        # ensure that the known tags are in the list
        tags = get_gnome_calculator_tags()["https://gitlab.gnome.org/GNOME/gnome-calculator.git"]
        for tag in data:
            found = False
            for tag2 in tags:
                if tag2["name"] == tag["name"]:
                    found = True
                    break
            assert found

    def test_branches(self):
        """ Check that using branches in a part instead of tags does work """
        snap, _, _, _ = self._load_test_file("gnome-boxes-test1.yaml",
                                             None,
                                             get_gnome_boxes_branches())
        _, tag_error = snap.process_parts()
        assert tag_error

    def test_gitlab_tags_download(self):
        """ Check that tag download from gitlab works as expected """
        gitobj = Gitlab(silent=True)
        gitobj.set_full_silent()
        self._load_secrets(gitobj)
        data = gitobj.get_tags("https://gitlab.gnome.org/GNOME/gnome-calculator",
                               "40.0", {"format": "%M.%m"})
        assert isinstance(data, list)
        # ensure that the known tags are in the list
        tags = get_gnome_calculator_tags()["https://gitlab.gnome.org/GNOME/gnome-calculator.git"]
        for tag in tags:
            found = False
            for tag2 in data:
                if tag2["name"] == tag["name"]:
                    found = True
                    break
            assert found

    def test_branch_no_permission(self):
        """ Checks that a file using source-branch without permission triggers
            an error """
        snap, _, _, _ = self._load_test_file("test_branch_no_permission.yaml",
                                             None,
                                             get_gnome_boxes_branches())
        _, tag_error = snap.process_parts()
        assert tag_error

    def test_branch_with_permission(self):
        """ Checks that a file using source-branch with permission doesn't
            trigger an error """
        snap, _, _, _ = self._load_test_file("test_branch_with_permission.yaml",
                                             None,
                                             get_gnome_boxes_branches())
        _, tag_error = snap.process_parts()
        assert not tag_error

    def test_no_tag_no_branch_no_permission(self):
        """ Checks that a file with neither source-branch nor source-tag without
            permission triggers an error """
        snap, _, _, _ = self._load_test_file("test_no_tag_no_branch_no_permission.yaml",
                                             None,
                                             get_gnome_boxes_branches())
        _, tag_error = snap.process_parts()
        assert tag_error

    def test_no_tag_no_branch_with_permission(self):
        """ Checks that a file with neither source-branch nor source-tag with
            permission doesn't trigger an error """
        snap, _, _, _ = self._load_test_file("test_no_tag_no_branch_with_permission.yaml",
                                             None,
                                             get_gnome_boxes_branches())
        _, tag_error = snap.process_parts()
        assert not tag_error

    def test_no_depth(self):
        """ Checks that a file without 'source-depth' triggers an error """
        snap, _, _, _ = self._load_test_file("test_no_depth.yaml",
                                             None,
                                             get_gnome_boxes_branches())
        _, tag_error = snap.process_parts()
        assert tag_error

    def test_invalid_uri(self):
        """ Checks that an invalid URI in a source field triggers an error """
        snap, _, github_pose, _ = self._load_test_file("test_invalid_url.yaml",
                                                       None,
                                                       get_gnome_boxes_branches())
        github_pose.set_uri_error(ValueError("Uri Error"))
        _, tag_error = snap.process_parts()
        assert tag_error

    def test_invalid_uri2(self):
        """ Checks that an invalid URI in a source field triggers an error """
        snap, _, github_pose, _ = self._load_test_file("test_invalid_url.yaml",
                                                       None,
                                                       get_gnome_boxes_branches())
        github_pose.set_uri_error(ConnectionError("Parameters Error"))
        _, tag_error = snap.process_parts()
        assert tag_error

    def test_comments_aligned(self):
        """ Checks that a comment with the right alignment
            is added as a child of the right element """
        data = self._base_load_test_file("aligned_comment.yaml")
        yaml_obj = ManageYAML(data)
        element = yaml_obj.get_part_element('gnome-system-monitor', 'source')
        assert isinstance(element, dict)
        assert 'data' in element
        assert element['data'] == 'source: https://gitlab.gnome.org/GNOME/gnome-system-monitor.git'
        assert 'level' in element
        assert element['level'] == 2
        assert 'separator' in element
        assert element['separator'] == '    '

    def test_comments_not_aligned(self):
        """ Checks that a comment with incorrect alignment
            is added as a child of the right element """
        data = self._base_load_test_file("unaligned_comment.yaml")
        yaml_obj = ManageYAML(data)
        element = yaml_obj.get_part_element('gnome-system-monitor', 'source')
        assert isinstance(element, dict)
        assert 'data' in element
        assert element['data'] == 'source: https://gitlab.gnome.org/GNOME/gnome-system-monitor.git'
        assert 'level' in element
        assert element['level'] == 2
        assert 'separator' in element
        assert element['separator'] == '    '

    def test_blank_line(self):
        """ Checks that a blank line is added as a child of the right element """
        data = self._base_load_test_file("blank_line.yaml")
        yaml_obj = ManageYAML(data)
        element = yaml_obj.get_part_element('gnome-system-monitor', 'source')
        assert isinstance(element, dict)
        assert 'data' in element
        assert element['data'] == 'source: https://gitlab.gnome.org/GNOME/gnome-system-monitor.git'
        assert 'level' in element
        assert element['level'] == 2
        assert 'separator' in element
        assert element['separator'] == '    '

    def test_no_true_or_false_on_option(self):
        """ Checks if the file doesn't follow the right format """
        data = self._base_load_test_file("snapcraft_no_true_false.yaml")
        snap = Snapcraft(True)
        snap.set_full_silent()
        with self.assertRaises(ValueError) as context:
            snap.load_external_data(data)
        assert context.exception

    def test_ignore_version_as_string(self):
        # pylint: disable=protected-access
        """ Tests the "ignore-version" option when parsing a version as a string """
        obj = ProcessVersion(silent=True)
        obj.set_full_silent()
        entry_format = {"format": "%M.%m.%R", "ignore-version": "2.43.6"}
        version = obj._get_version("testpart", "2.43.6", entry_format, False)
        assert version is None
        assert ("The 'ignore-version' entry in testpart is neither a string, nor a list."
                not in obj._error_list)
        version = obj._get_version("testpart", "3.42.1", entry_format, False)
        assert str(version) == "3.42.1"
        assert ("The 'ignore-version' entry in testpart is neither a string, nor a list."
                not in obj._error_list)

    def test_ignore_version_as_list(self):
        # pylint: disable=protected-access
        """ Tests the "ignore-version" option when parsing a version as a list of versions """
        obj = ProcessVersion(silent=True)
        obj.set_full_silent()
        entry_format = {"format": "%M.%m.%R", "ignore-version": ["2.43.6", "3.2.4"]}
        version = obj._get_version("testpart", "2.43.6", entry_format, False)
        assert version is None
        assert ("The 'ignore-version' entry in testpart is neither a string, nor a list."
                not in obj._error_list)
        assert ("The 'ignore-version' entry in testpart contains an element that is not a string."
                not in obj._error_list)
        version = obj._get_version("testpart", "3.2.4", entry_format, False)
        assert version is None
        assert ("The 'ignore-version' entry in testpart is neither a string, nor a list."
                not in obj._error_list)
        assert ("The 'ignore-version' entry in testpart contains an element that is not a string."
                not in obj._error_list)
        version = obj._get_version("testpart", "3.42.1", entry_format, False)
        assert str(version) == "3.42.1"
        assert ("The 'ignore-version' entry in testpart is neither a string, nor a list."
                not in obj._error_list)
        assert ("The 'ignore-version' entry in testpart contains an element that is not a string."
                not in obj._error_list)

    def test_ignore_version_as_other_thing(self):
        # pylint: disable=protected-access
        """ Tests that "ignore-version" shows an error when the version is neither
            a string nor a list """
        obj = ProcessVersion(silent=True)
        obj.set_full_silent()
        entry_format = {"format": "%M.%m.%R", "ignore-version": {}}
        with self.assertRaises(ValueError) as context:
            obj._get_version("testpart", "2.43.6", entry_format, False)
        assert context.exception
        assert ("The 'ignore-version' entry in testpart is neither a string, nor a list."
                in obj._error_list)
        assert ("The 'ignore-version' entry in testpart contains an element that is not a string."
                not in obj._error_list)

    def test_ignore_version_contains_other_thing(self):
        # pylint: disable=protected-access
        """ Tests that "ignore-version" shows an error when the version is neither
            a string or a list """
        obj = ProcessVersion(silent=True)
        obj.set_full_silent()
        entry_format = {"format": "%M.%m.%R", "ignore-version": ["1.3.4", ["4.5", "8"]]}
        with self.assertRaises(ValueError) as context:
            obj._get_version("testpart", "2.43.6", entry_format, False)
        assert context.exception
        assert ("The 'ignore-version' entry in testpart is neither a string, nor a list."
                not in obj._error_list)
        assert ("The 'ignore-version' entry in testpart contains an element that is not a string."
                in obj._error_list)

    def test_no_source_or_local_source(self):
        """ tests if a part without source or with a local source is ignored """
        snap, _, _, _ = self._load_test_file("gnome-calculator-test1-local-source.yaml",
                                             get_gnome_calculator_tags())
        data, _ = snap.process_parts()
        assert len(data) == 2
        assert data[0] is None
        assert data[1] is None


class GitPose:
    """ Helper class. It emulates a GitClass class, to allow to test
        classes that depend on it, without having to rely on an external
        github or gitlab repository """
    def __init__(self):
        self._tags = {}
        self._branches = {}
        self._uri_error = None
        self._silent = True
        self._full_silent = False

    def set_full_silent(self):
        """ Implements the method to avoid errors. """
        self._full_silent = True

    def set_uri_error(self, new_uri_error: Exception):
        """ Sets whether the object will emulate an error in the URI or
            work as expected """
        self._uri_error = new_uri_error

    def set_secrets(self, data):
        """ emulates the set_secrets() method. """

    def set_tags(self, tags):
        """ Sets the tags that will be returned by this object when asked """
        self._tags = tags

    def set_branches(self, branches):
        """ Sets the branches that will be returned by this object when asked """
        self._branches = branches

    def get_tags(self, source, current_tag=None, version_format=None):
        # pylint: disable=unused-argument
        """ Implements the get_tags() method of GitClass """
        if self._uri_error is not None:
            raise self._uri_error
        if self._tags is None:
            return []
        if source in self._tags:
            return self._tags[source]
        return []

    def get_branches(self, source):
        """ Implements the get_branches() method of GitClass """
        if self._branches is None:
            return []
        if source in self._branches:
            return self._branches[source]
        return []


def get_gnome_boxes_branches():
    """ Returns a plausible list of branches for several tests """
    return {
        "https://gitlab.com/libvirt/libvirt.git":
        [
            {'name': 'master', 'date': 0},
            {'name': 'v0.10.2-maint', 'date': 0},
            {'name': 'v0.8.3-maint', 'date': 0},
            {'name': 'v0.9.11-maint', 'date': 0},
            {'name': 'v0.9.12-maint', 'date': 0},
            {'name': 'v0.9.6-maint', 'date': 0},
            {'name': 'v1.0.0-maint', 'date': 0},
            {'name': 'v1.0.1-maint', 'date': 0},
            {'name': 'v1.0.2-maint', 'date': 0},
            {'name': 'v1.0.3-maint', 'date': 0},
            {'name': 'v1.0.4-maint', 'date': 0},
            {'name': 'v1.0.5-maint', 'date': 0},
            {'name': 'v1.0.6-maint', 'date': 0},
            {'name': 'v1.1.0-maint', 'date': 0},
            {'name': 'v1.1.1-maint', 'date': 0},
            {'name': 'v1.1.2-maint', 'date': 0},
            {'name': 'v1.1.3-maint', 'date': 0},
            {'name': 'v1.1.4-maint', 'date': 0},
            {'name': 'v1.2.0-maint', 'date': 0},
            {'name': 'v1.2.1-maint', 'date': 0},
            {'name': 'v1.2.10-maint', 'date': 0},
            {'name': 'v1.2.11-maint', 'date': 0},
            {'name': 'v1.2.12-maint', 'date': 0},
            {'name': 'v1.2.13-maint', 'date': 0},
            {'name': 'v1.2.14-maint', 'date': 0},
            {'name': 'v1.2.15-maint', 'date': 0},
            {'name': 'v1.2.16-maint', 'date': 0},
            {'name': 'v1.2.17-maint', 'date': 0},
            {'name': 'v1.2.18-maint', 'date': 0},
            {'name': 'v1.2.19-maint', 'date': 0},
            {'name': 'v1.2.2-maint', 'date': 0},
            {'name': 'v1.2.20-maint', 'date': 0},
            {'name': 'v1.2.21-maint', 'date': 0},
            {'name': 'v1.2.3-maint', 'date': 0},
            {'name': 'v1.2.4-maint', 'date': 0},
            {'name': 'v1.2.5-maint', 'date': 0},
            {'name': 'v1.2.6-maint', 'date': 0},
            {'name': 'v1.2.7-maint', 'date': 0},
            {'name': 'v1.2.8-maint', 'date': 0},
            {'name': 'v1.2.9-maint', 'date': 0},
            {'name': 'v1.3.0-maint', 'date': 0},
            {'name': 'v1.3.1-maint', 'date': 0},
            {'name': 'v1.3.2-maint', 'date': 0},
            {'name': 'v1.3.3-maint', 'date': 0},
            {'name': 'v1.3.4-maint', 'date': 0},
            {'name': 'v1.3.5-maint', 'date': 0},
            {'name': 'v2.0-maint', 'date': 0},
            {'name': 'v2.1-maint', 'date': 0},
            {'name': 'v2.2-maint', 'date': 0},
            {'name': 'v3.0-maint', 'date': 0},
            {'name': 'v3.2-maint', 'date': 0},
            {'name': 'v3.7-maint', 'date': 0},
            {'name': 'v4.1-maint', 'date': 0},
            {'name': 'v4.10-maint', 'date': 0},
            {'name': 'v4.2-maint', 'date': 0},
            {'name': 'v4.3-maint', 'date': 0},
            {'name': 'v4.4-maint', 'date': 0},
            {'name': 'v4.5-maint', 'date': 0},
            {'name': 'v4.6-maint', 'date': 0},
            {'name': 'v4.7-maint', 'date': 0},
            {'name': 'v4.8-maint', 'date': 0},
            {'name': 'v4.9-maint', 'date': 0},
            {'name': 'v5.0-maint', 'date': 0},
            {'name': 'v5.1-maint', 'date': 0},
            {'name': 'v5.1.0-maint', 'date': 0},
            {'name': 'v5.2-maint', 'date': 0},
            {'name': 'v5.3-maint', 'date': 0}],
        "https://gitlab.gnome.org/GNOME/tracker.git":
        [
            {'name': '34-build-failure-with-werror-format-security', 'date': 0},
            {'name': 'abderrahim/build-fix', 'date': 0},
            {'name': 'api-cleanup', 'date': 0},
            {'name': 'configurable-bus-type', 'date': 0},
            {'name': 'crawler-max-depth', 'date': 0},
            {'name': 'data-provider-monitor-interface', 'date': 0},
            {'name': 'decorator-memory-reduction', 'date': 0},
            {'name': 'domain-ontologies', 'date': 0},
            {'name': 'external-libstemmer', 'date': 0},
            {'name': 'fix-version', 'date': 0},
            {'name': 'follow-symlinks', 'date': 0},
            {'name': 'fts-property-names-cleanup', 'date': 0},
            {'name': 'fts4', 'date': 0},
            {'name': 'functional-test-fixes-bug-696172', 'date': 0},
            {'name': 'gdbus-porting', 'date': 0},
            {'name': 'hashtable-ordering-2.1', 'date': 0},
            {'name': 'jolla-upstreaming', 'date': 0},
            {'name': 'master', 'date': 0},
            {'name': 'maxcardinality-change-support', 'date': 0},
            {'name': 'maxcardinality-change-support-rebased', 'date': 0},
            {'name': 'media-art-detect', 'date': 0},
            {'name': 'meson-final', 'date': 0},
            {'name': 'miner-twitter', 'date': 0},
            {'name': 'oscp', 'date': 0},
            {'name': 'pdf-extractor-no-forks', 'date': 0},
            {'name': 'ricotz/vala', 'date': 0},
            {'name': 'rss-update', 'date': 0},
            {'name': 'sam/README', 'date': 0},
            {'name': 'sam/README-updates', 'date': 0},
            {'name': 'sam/app-domains', 'date': 0},
            {'name': 'sam/ci', 'date': 0},
            {'name': 'sam/ci-docs', 'date': 0},
            {'name': 'sam/ci-sanitize', 'date': 0},
            {'name': 'sam/circular-dep-fix', 'date': 0},
            {'name': 'sam/comment', 'date': 0},
            {'name': 'sam/common-file-utils', 'date': 0},
            {'name': 'sam/coverity-fix', 'date': 0},
            {'name': 'sam/diagrams', 'date': 0},
            {'name': 'sam/functional-tests-pep8', 'date': 0},
            {'name': 'sam/index-file-sync', 'date': 0},
            {'name': 'sam/index-mount-points', 'date': 0},
            {'name': 'sam/index-mount-points-2', 'date': 0},
            {'name': 'sam/info-fix', 'date': 0},
            {'name': 'sam/introspection-fix', 'date': 0},
            {'name': 'sam/meson-0.60', 'date': 0},
            {'name': 'sam/miner-fs-ignore-non-files', 'date': 0},
            {'name': 'sam/namespace-c++', 'date': 0},
            {'name': 'sam/remove-libuuid', 'date': 0},
            {'name': 'sam/run-uninstalled-fixes', 'date': 0},
            {'name': 'sam/share-sandboxes', 'date': 0},
            {'name': 'sam/show-debug', 'date': 0},
            {'name': 'sam/slow-tests', 'date': 0},
            {'name': 'sam/test-utils', 'date': 0},
            {'name': 'sam/tracker-2.3-developer-experience', 'date': 0},
            {'name': 'sam/tracker-3.0-functional-tests', 'date': 0},
            {'name': 'sam/tracker-resource-avoid-invalid-sparql', 'date': 0},
            {'name': 'sam/uncrustify', 'date': 0},
            {'name': 'sam/web-overview', 'date': 0},
            {'name': 'sam/website-docs', 'date': 0},
            {'name': 'sam/website-link', 'date': 0},
            {'name': 'sam/wiki-to-website', 'date': 0},
            {'name': 'sparql-ontology-tree', 'date': 0},
            {'name': 'subtree-crawling', 'date': 0},
            {'name': 'tintou/doc-update', 'date': 0},
            {'name': 'tracker-0.10', 'date': 0},
            {'name': 'tracker-0.12', 'date': 0},
            {'name': 'tracker-0.14', 'date': 0},
            {'name': 'tracker-0.16', 'date': 0},
            {'name': 'tracker-0.6', 'date': 0},
            {'name': 'tracker-0.8', 'date': 0},
            {'name': 'tracker-1.0', 'date': 0},
            {'name': 'tracker-1.10', 'date': 0},
            {'name': 'tracker-1.12', 'date': 0},
            {'name': 'tracker-1.2', 'date': 0},
            {'name': 'tracker-1.4', 'date': 0},
            {'name': 'tracker-1.6', 'date': 0},
            {'name': 'tracker-1.8', 'date': 0},
            {'name': 'tracker-2.1', 'date': 0},
            {'name': 'tracker-2.2', 'date': 0},
            {'name': 'tracker-2.3', 'date': 0},
            {'name': 'tracker-3.0', 'date': 0},
            {'name': 'tracker-3.1', 'date': 0},
            {'name': 'tracker-3.2', 'date': 0},
            {'name': 'tracker-3.3', 'date': 0},
            {'name': 'tracker-3.4', 'date': 0},
            {'name': 'tracker-cmd', 'date': 0},
            {'name': 'trackerutils-arch-independent', 'date': 0},
            {'name': 'updated-gtester', 'date': 0},
            {'name': 'wip/carlosg/automatic-store-shutdown', 'date': 0},
            {'name': 'wip/carlosg/avahi', 'date': 0},
            {'name': 'wip/carlosg/ci-playground2', 'date': 0},
            {'name': 'wip/carlosg/direct-rewrite', 'date': 0},
            {'name': 'wip/carlosg/domain-ontologies', 'date': 0},
            {'name': 'wip/carlosg/double-precision', 'date': 0},
            {'name': 'wip/carlosg/downgrade-meson-version', 'date': 0},
            {'name': 'wip/carlosg/drop-autotools', 'date': 0},
            {'name': 'wip/carlosg/fix-bijiben-flatpak', 'date': 0},
            {'name': 'wip/carlosg/fix-tracker-search', 'date': 0},
            {'name': 'wip/carlosg/gi-docgen', 'date': 0},
            {'name': 'wip/carlosg/insert-delete-triggers', 'date': 0},
            {'name': 'wip/carlosg/issue-40', 'date': 0},
            {'name': 'wip/carlosg/issue-56', 'date': 0},
            {'name': 'wip/carlosg/legalese-cardinality', 'date': 0},
            {'name': 'wip/carlosg/libtracker-miner-cleanups', 'date': 0},
            {'name': 'wip/carlosg/meson-fixes', 'date': 0},
            {'name': 'wip/carlosg/meson-system-dirs', 'date': 0},
            {'name': 'wip/carlosg/ontlogy-tests-no-skip', 'date': 0},
            {'name': 'wip/carlosg/property-paths', 'date': 0},
            {'name': 'wip/carlosg/remote-module-extension', 'date': 0},
            {'name': 'wip/carlosg/resource-deletes', 'date': 0},
            {'name': 'wip/carlosg/resource-leak-fix', 'date': 0},
            {'name': 'wip/carlosg/sparql-parser-ng', 'date': 0},
            {'name': 'wip/carlosg/sparql-shell', 'date': 0},
            {'name': 'wip/carlosg/trigger-filter-parent-on-monitor-events', 'date': 0},
            {'name': 'wip/carlosg/unrestricted-predicates', 'date': 0},
            {'name': 'wip/collect-bug-info', 'date': 0},
            {'name': 'wip/ernestask/43', 'date': 0},
            {'name': 'wip/fts5', 'date': 0},
            {'name': 'wip/garnacho/sparql1.1', 'date': 0},
            {'name': 'wip/index-mount-points', 'date': 0},
            {'name': 'wip/jfelder/audio-writeback', 'date': 0},
            {'name': 'wip/jtojnar/2.1-dist-fix', 'date': 0},
            {'name': 'wip/lantw/dont-hard-code-usr-bin-python2', 'date': 0},
            {'name': 'wip/mschraal/meson-log-domain', 'date': 0},
            {'name': 'wip/mschraal/python3-port', 'date': 0},
            {'name': 'wip/passive-extraction', 'date': 0},
            {'name': 'wip/removable-device-completed', 'date': 0},
            {'name': 'wip/ricotz/type-args', 'date': 0},
            {'name': 'wip/rishi/non-native', 'date': 0},
            {'name': 'wip/rishi/tracker-sparql-connection-peer-to-peer', 'date': 0},
            {'name': 'wip/sam/carlosg/direct-rewrite', 'date': 0},
            {'name': 'wip/sam/private-store', 'date': 0},
            {'name': 'wip/sam/test-sqlite', 'date': 0},
            {'name': 'wip/split/core', 'date': 0},
            {'name': 'wip/split/miner-fs', 'date': 0},
            {'name': 'wip/split/rss', 'date': 0},
            {'name': 'wip/sthursfield/debian10-hacks', 'date': 0},
            {'name': 'wip/tintou/fix-doc', 'date': 0}
        ],
        "https://gitlab.gnome.org/GNOME/gnome-boxes.git":
        [
            {'name': 'account-for-interference-on-reboot-count', 'date': 0},
            {'name': 'alatiera/sourceview', 'date': 0},
            {'name': 'bundle-mks', 'date': 0},
            {'name': 'check-kvm-user', 'date': 0},
            {'name': 'create-qcow2-with-compat1.1', 'date': 0},
            {'name': 'flatpak-net-bridge', 'date': 0},
            {'name': 'flatpak-use-vala-lang-server-sdk', 'date': 0},
            {'name': 'gnome-3-10', 'date': 0},
            {'name': 'gnome-3-12', 'date': 0},
            {'name': 'gnome-3-14', 'date': 0},
            {'name': 'gnome-3-16', 'date': 0},
            {'name': 'gnome-3-18', 'date': 0},
            {'name': 'gnome-3-20', 'date': 0},
            {'name': 'gnome-3-22', 'date': 0},
            {'name': 'gnome-3-24', 'date': 0},
            {'name': 'gnome-3-26', 'date': 0},
            {'name': 'gnome-3-28', 'date': 0},
            {'name': 'gnome-3-30', 'date': 0},
            {'name': 'gnome-3-32', 'date': 0},
            {'name': 'gnome-3-34', 'date': 0},
            {'name': 'gnome-3-36', 'date': 0},
            {'name': 'gnome-3-38', 'date': 0},
            {'name': 'gnome-3-4', 'date': 0},
            {'name': 'gnome-3-6', 'date': 0},
            {'name': 'gnome-3-8', 'date': 0},
            {'name': 'gnome-40', 'date': 0},
            {'name': 'gnome-40-fix-run-in-bg', 'date': 0},
            {'name': 'gnome-41', 'date': 0},
            {'name': 'gnome-41-fix-clones-regression', 'date': 0},
            {'name': 'gnome-42', 'date': 0},
            {'name': 'gnome-43', 'date': 0},
            {'name': 'gnome-44', 'date': 0},
            {'name': 'libvirt-socket-path-long-2022', 'date': 0},
            {'name': 'main', 'date': 0},
            {'name': 'osdb-prefer-x86_64_resources-by-default', 'date': 0},
            {'name': 'restore-support-to-download', 'date': 0},
            {'name': 'update-po-files', 'date': 0},
            {'name': 'wip/arm', 'date': 0},
            {'name': 'wip/codespell-ci', 'date': 0},
            {'name': 'wip/disable-secure-boot', 'date': 0},
            {'name': 'wip/dont-continue-installations-on-restart', 'date': 0},
            {'name': 'wip/empty-state-update-graphic', 'date': 0},
            {'name': 'wip/feborges/flatpak-net-bridge', 'date': 0},
            {'name': 'wip/feborges/no-filesystem-access', 'date': 0},
            {'name': 'wip/new-properties-dialog', 'date': 0},
            {'name': 'wip/sam/tracker3', 'date': 0},
            {'name': 'wip/support-windows-11', 'date': 0},
            {'name': 'workaround-audio-regression', 'date': 0}
        ]
    }


def get_gnome_calculator_tags():
    """ Returns a plausible list of tags for several tests """
    return {"https://gitlab.gnome.org/GNOME/gnome-calculator.git":
            [
                {'name': '44.0',
                 'date': datetime.datetime(2023, 3, 17, 22, 17, 18,
                                           tzinfo=datetime.timezone(
                                            datetime.timedelta(seconds=7200)))},
                {'name': '44.rc',
                 'date': datetime.datetime(2023, 3, 3, 22, 33, 23,
                                           tzinfo=datetime.timezone(
                                            datetime.timedelta(seconds=7200)))},
                {'name': '44.beta',
                 'date': datetime.datetime(2023, 2, 11, 21, 31, 11,
                                           tzinfo=datetime.timezone(
                                            datetime.timedelta(seconds=7200)))},
                {'name': '43.0.1',
                 'date': datetime.datetime(2022, 9, 16, 20, 40, 1,
                                           tzinfo=datetime.timezone(
                                            datetime.timedelta(seconds=10800)))},
                {'name': '43.0',
                 'date': datetime.datetime(2022, 9, 16, 19, 58, 24,
                                           tzinfo=datetime.timezone(
                                            datetime.timedelta(seconds=10800)))},
                {'name': '43.rc',
                 'date': datetime.datetime(2022, 9, 2, 23, 14, 40,
                                           tzinfo=datetime.timezone(
                                            datetime.timedelta(seconds=10800)))},
                {'name': '43.alpha',
                 'date': datetime.datetime(2022, 7, 8, 16, 48, 43,
                                           tzinfo=datetime.timezone(
                                            datetime.timedelta(seconds=10800)))},
                {'name': '42.2',
                 'date': datetime.datetime(2022, 7, 1, 23, 15, 12,
                                           tzinfo=datetime.timezone(
                                            datetime.timedelta(seconds=10800)))},
                {'name': '42.1',
                 'date': datetime.datetime(2022, 5, 27, 19, 27, 52,
                                           tzinfo=datetime.timezone(
                                            datetime.timedelta(seconds=10800)))},
                {'name': '42.0',
                 'date': datetime.datetime(2022, 3, 19, 22, 15, 55,
                                           tzinfo=datetime.timezone(
                                            datetime.timedelta(seconds=7200)))},
                {'name': '42.rc',
                 'date': datetime.datetime(2022, 3, 6, 8, 15, 44,
                                           tzinfo=datetime.timezone(
                                            datetime.timedelta(seconds=7200)))},
                {'name': '42.beta',
                 'date': datetime.datetime(2022, 2, 13, 22, 0, 5,
                                           tzinfo=datetime.timezone(
                                            datetime.timedelta(seconds=7200)))},
                {'name': '42.alpha',
                 'date': datetime.datetime(2022, 1, 8, 23, 22, 56,
                                           tzinfo=datetime.timezone(
                                            datetime.timedelta(seconds=7200)))},
                {'name': '41.1',
                 'date': datetime.datetime(2021, 12, 6, 8, 47, 24,
                                           tzinfo=datetime.timezone(
                                            datetime.timedelta(seconds=7200)))},
                {'name': '41.0',
                 'date': datetime.datetime(2021, 9, 18, 22, 40, 23,
                                           tzinfo=datetime.timezone(
                                            datetime.timedelta(seconds=10800)))},
                {'name': '41.rc',
                 'date': datetime.datetime(2021, 9, 4, 20, 28, 37,
                                           tzinfo=datetime.timezone(
                                            datetime.timedelta(seconds=10800)))},
                {'name': '41.alpha',
                 'date': datetime.datetime(2021, 7, 10, 8, 44, 20,
                                           tzinfo=datetime.timezone(
                                            datetime.timedelta(seconds=10800)))},
                {'name': '40.1',
                 'date': datetime.datetime(2021, 4, 30, 16, 38, 38,
                                           tzinfo=datetime.timezone(
                                            datetime.timedelta(seconds=10800)))},
                {'name': '40.0',
                 'date': datetime.datetime(2021, 3, 19, 20, 32, 6,
                                           tzinfo=datetime.timezone(
                                            datetime.timedelta(seconds=7200)))}
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
