""" Processes a YAML file to get the list of available updates for
    each part, or return a new YAML with each part's version tag
    updated to the last version available in each source repository """

import urllib
import base64
import re
import time
import os
import datetime
import sys
from typing import Optional
import requests
import yaml

import packaging.version
import debian.debian_support


class Colors:
    # pylint: disable=too-few-public-methods
    """ Container class to define the colors for the messages """
    def __init__(self):
        red = "\033[31m"
        green = "\033[32m"
        yellow = "\033[33m"
        cyan = "\033[36m"

        self.reset = "\033[0m"
        self.clearline = "\033[2K"

        self.critical = red
        self.warning = yellow
        self.all_ok = green
        self.note = cyan

    def clear_line(self):
        """ Restore the colors to the default ones

        This must be called after showing a piece of text with any of
        the previous colors, to go back to the default color."""
        print(self.clearline, end="\r", file=sys.stderr)


class ProcessVersion:
    # pylint: disable=too-few-public-methods
    """ Base code to process a version number from a tag

    Implements the base code to parse a version number based on the
    version_format tag in a snapcraft.yaml file."""
    def __init__(self, silent=False):
        super().__init__()
        self._silent = silent
        self._colors = Colors()
        self._last_part = None
        self._error_list = []
        self._full_silent = False

    def set_full_silent(self):
        """ Fully disables all the messages, not only the warnings or
            the current process. Useful for testings."""
        self._full_silent = True

    def _print_message(self, part, message, source=None, override_silent=False):
        # pylint: disable=too-many-function-args
        if self._silent and not override_silent:
            return
        self._print_error(part, None, message, source, False)

    def _print_error(self, part, use_color, message, source=None, extra_cr=False):
        # pylint: disable=too-many-arguments
        self._error_list.append(message)
        if self._full_silent:
            return
        if part != self._last_part:
            print(f"Part: {self._colors.note}{part}{self._colors.reset}"
                  f"{f' ({source})' if source else ''}", file=sys.stderr)
            self._last_part = part
        if message is not None:
            print("  ", end="", file=sys.stderr)
            if use_color is not None:
                print(use_color, end="", file=sys.stderr)
            print(message, end="", file=sys.stderr)
            if use_color is not None:
                print(self._colors.reset, file=sys.stderr)
        if extra_cr:
            print("", file=sys.stderr)

    @staticmethod
    def _read_number(text):
        number = 0
        if (len(text) == 0) or (text[0] not in '0123456789'):
            return None, text
        while (len(text) > 0) and (text[0] in '0123456789'):
            number *= 10
            number += int(text[0])
            text = text[1:]
        return number, text

    def _checkopt(self, option, dictionary):
        """ Returns True if an option is in the dictionary and it's True.
            If it's False or it isn't in the dictionary, it returns False. """
        if not isinstance(dictionary, dict):
            raise ValueError(f"The element {dictionary} isn't a dictionary; "
                             "ensure that your options have the following "
                             "format: XXXXXXXX: true")
        return (option in dictionary) and dictionary[option]

    def _get_version(self, part_name, entry, entry_format, check):
        """ Gets the version number from a tag, and filters it against
            the rules set in the part's version-format entry."""
        # pylint: disable=too-many-return-statements, too-many-branches
        if "format" not in entry_format:
            if check:
                self._print_error(part_name, self._colors.critical,
                                  "Missing tag version format for "
                                  f"{part_name}.")
            return None  # unknown format
        # Check for variations in the version format and beta releases.
        if '%V' in entry_format['format']:
            if not entry.startswith(entry_format['format'].split('%')[0]):
                return None
            try:
                version = packaging.version.parse(
                        entry[len(entry_format['format'].split('%')[0]):])
                if (("lower-than" in entry_format) and
                        (version >= packaging.version.parse(
                            str(entry_format["lower-than"])))):
                    return None
                return version
            except packaging.version.InvalidVersion:
                version = debian.debian_support.Version(
                    entry[len(entry_format['format'].split('%')[0]):])
                if (("lower-than" in entry_format) and
                        (version >= debian.debian_support.Version(
                            str(entry_format["lower-than"])))):
                    return None
                return version
        major = 0
        minor = 0
        revision = 0
        # space is "no element". Adding it in front of the first block simplifies the code
        fmt = (" " + entry_format["format"]).split("%")
        for part in fmt:
            if part[0] != ' ':
                number, entry = self._read_number(entry)
                if number is None:
                    return None  # not found a number when expected
                match part[0]:
                    case 'M':
                        major = number
                    case 'm':
                        minor = number
                    case 'R':
                        revision = number
            part = part[1:]
            if len(part) == 0:
                continue
            if not entry.startswith(part):
                return None
            entry = entry[len(part):]
        version = packaging.version.parse(f"{major}.{minor}.{revision}")

        if "ignore-version" in entry_format:
            to_ignore = entry_format["ignore-version"]
            if isinstance(to_ignore, str):
                if version == packaging.version.parse(to_ignore):
                    return None
            elif isinstance(to_ignore, list):
                for ignore_version in to_ignore:
                    if not isinstance(ignore_version, str):
                        message = (f"The 'ignore-version' entry in {part_name} "
                                   "contains an element that is not a string.")
                        self._print_error(part_name, self._colors.critical, message)
                        raise ValueError(message)
                    if version == packaging.version.parse(ignore_version):
                        return None
            else:
                message = (f"The 'ignore-version' entry in {part_name} is neither a string, "
                           "nor a list.")
                self._print_error(part_name, self._colors.critical, message)
                raise ValueError(message)

        if (("lower-than" in entry_format) and
                (version >= packaging.version.parse(str(entry_format["lower-than"])))):
            return None
        if self._checkopt("ignore-odd-minor", entry_format) and ((minor % 2) == 1):
            return None
        if self._checkopt("no-9x-revisions", entry_format) and (revision >= 90):
            return None
        if self._checkopt("no-9x-minors", entry_format) and (minor >= 90):
            return None
        return version


class GitClass(ProcessVersion):
    """ Base class to get access to a GIT repository

    Implements the base functionality to access a remote GIT repository,
    either Github or Gitlab type, and use a REST API to obtain data. """
    def __init__(self, repo_type: str, silent=False):
        super().__init__(silent)
        self._token = None
        self._user = None
        self._repo_type = repo_type
        self._current_tag = None

    def set_secrets(self, secrets):
        """ Configure the secrets for this repository

        The secrets are things like username and access tokens."""
        if (self._repo_type == 'github') and 'github' in secrets:
            self._user = secrets['github']['user']
            self._token = secrets['github']['token']

    def set_secret(self, secret: str, value):
        """ Configure an specific secret """
        if secret == 'user':
            self._user = value
        elif secret == 'token':
            self._token = value

    def _read_uri(self, uri: str):
        # pylint: disable=bare-except
        if not self._silent:
            print(f"Asking URI {uri}     ", end="\r", file=sys.stderr)
        while True:
            try:
                if (self._user is not None) and (self._token is not None):
                    response = requests.get(uri, auth=requests.auth.HTTPBasicAuth(
                                            self._user, self._token), timeout=30)
                else:
                    response = requests.get(uri, timeout=30)
                break
            except (requests.ConnectionError, requests.Timeout):
                if not self._silent:
                    print(f"Retrying URI {uri}     ", end="\r", file=sys.stderr)
                time.sleep(1)
        return response

    def _stop_download(self, data):
        # pylint: disable=unused-argument
        return False

    def _read_pages(self, uri: str) -> Optional[list]:
        elements = []
        while uri is not None:
            response = self._read_uri(uri)
            if response.status_code != 200:
                message = f"Status code {response.status_code} when asking for {uri}"
                if not self._silent:
                    print(f"{self._colors.critical}{message}{self._colors.reset}", file=sys.stderr)
                raise ConnectionError(message)
            headers = response.headers
            data = response.json()
            for entry in data:
                elements.append(entry)
            if self._stop_download(data):
                break
            uri = None
            if "Link" in headers:
                link = headers["link"]
                entries = link.split(",")
                for entry in entries:
                    if 'rel="next"' not in entry:
                        continue
                    p_left = entry.find("<")
                    p_right = entry.find(">")
                    uri = entry[p_left+1:p_right]
                    break
        if not self._silent:
            self._colors.clear_line()
        return elements

    def _read_page(self, uri: str) -> Optional[dict]:
        response = self._read_uri(uri)
        if response.status_code != 200:
            message = f"Status code {response.status_code} when asking for {uri}"
            if not self._silent:
                print(f"{self._colors.critical}{message}{self._colors.reset}", file=sys.stderr)
            raise ConnectionError(message)
        data = response.json()
        return data

    def _get_uri(self, repository, min_elements):
        """ Returns an URI object for an specific repository, and also ensures
            that the URI is valid. Throws an exception if the protocol or the
            URI format is not recognized. """
        repository = repository.strip()
        if repository[-4:] == '.git':
            repository = repository[:-4]
        uri = urllib.parse.urlparse(repository)
        elements = uri.path.split("/")
        if uri.scheme not in ['http', 'https', 'git']:
            message = f"Unrecognized protocol in repository {repository}"
            print(f"{self._colors.critical}{message}{self._colors.reset}", file=sys.stderr)
            raise ValueError(message)
        elements = uri.path.split("/")
        if len(elements) < min_elements:
            message = f"Invalid uri format for repository {repository}"
            print(f"{self._colors.critical}{message}{self._colors.reset}", file=sys.stderr)
            raise ValueError(message)
        return uri

    @staticmethod
    def _rb(text):
        """ Remove trailing and heading '/' characters, to simplify building URIs """
        while (len(text) > 0) and (text[0] == '/'):
            text = text[1:]
        while (len(text) > 0) and (text[-1] == '/'):
            text = text[:-1]
        return text

    @staticmethod
    def join_url(*args):
        """ Join several elements into a single URL """
        if len(args) == 0:
            return ""
        output = args[0]
        for element in args[1:]:
            if output[-1] == '/':
                output = output[:-1]
            if element[0] == '/':
                element = element[1:]
            output += '/' + element
        return output


class Github(GitClass):
    """ Implements access to Github GIT repositories """
    def __init__(self, silent=False):
        super().__init__("github", silent)
        self._api_url = 'https://api.github.com/repos/'

    def _is_github(self, repository: str):
        """ Evaluates the URI of a repository and returns an URI
            object with it, but only if it is a Github URI. """
        uri = self._get_uri(repository, 3)
        if uri.netloc not in ["github.com", "www.github.com"]:
            return None
        return uri

    def get_branches(self, repository: str) -> Optional[list]:
        """ Returns a list of branches for this repository """
        uri = self._is_github(repository)
        if uri is None:
            return None
        branch_command = self.join_url(self._api_url, uri.path, 'branches')
        return self._read_pages(branch_command)

    def _stop_download(self, data) -> bool:
        if self._current_tag is None:
            return False
        for entry in data:
            if ('name' in entry) and (self._current_tag == entry['name']):
                return True
        return False

    def get_tags(self, repository: str, current_tag=None,
                 version_format=None) -> Optional[list]:
        """ Returns a list of tags for this repository """
        if version_format is None:
            version_format = {}
        uri = self._is_github(repository)
        if uri is None:
            return None

        self._current_tag = current_tag
        tag_command = self.join_url(self._rb(self._api_url), self._rb(uri.path),
                                    'tags?sort=created&direction=desc')
        data = self._read_pages(tag_command)
        if not data:
            return None
        tags = []
        self._current_tag = None
        for tag in data:
            parsed_version = self._get_version("", tag['name'], version_format, False)
            if parsed_version is None:
                continue
            tag_info = self._read_page(tag['commit']['url'])
            if tag_info is None:
                continue
            if 'commiter' in tag_info['commit']:
                date = tag_info['commit']['committer']['date']
            else:
                date = tag_info['commit']['author']['date']
            tags.append({"name": tag['name'],
                         "date": datetime.datetime.strptime(date, "%Y-%m-%dT%H:%M:%SZ")})
            if (current_tag is not None) and (current_tag == tag['name']):
                break
        if not self._silent:
            self._colors.clear_line()
        return tags

    def get_file(self, repository: str, file_path: str) -> Optional[bytes]:
        """ Returns a json with the contents of a file of the repository """
        uri = self._is_github(repository)
        if uri is None:
            return None

        tag_command = self.join_url(self._rb(self._api_url), self._rb(uri.path),
                                    'contents', file_path)
        data = self._read_page(tag_command)
        if (data is None) or ("content" not in data):
            return None
        return base64.b64decode(data['content'])


class Gitlab(GitClass):
    """ Implements access to Gitlab GIT repositories """
    def __init__(self, silent=False):
        super().__init__("gitlab", silent)

    def _is_gitlab(self, repository):
        """ Evaluates the URI of a repository and returns an URI
            object with it, but only if it is a Gitlab URI. """
        uri = self._get_uri(repository, 3)
        # Check for gitlab instance used by debian
        if "salsa" in uri.netloc:
            return uri
        if "gitlab" not in uri.netloc:
            return None
        return uri

    @staticmethod
    def _project_name(uri):
        name = uri.path
        while name[0] == '/':
            name = name[1:]
        return name.replace('/', '%2F')

    def get_branches(self, repository) -> Optional[list]:
        """ Returns a list of branches for this repository """
        uri = self._is_gitlab(repository)
        if uri is None:
            return None

        branch_command = self.join_url(uri.scheme + '://', uri.netloc, 'api/v4/projects',
                                       self._project_name(uri), 'repository/branches')
        data = self._read_pages(branch_command)
        if not data:
            return None
        branches = []
        for branch in data:
            element = {"name": branch['name']}
            if "commited_date" in branch["commit"]:
                element["date"] = branch["commit"]["commited_date"]
            elif "created_at" in branch["commit"]:
                element["date"] = branch["commit"]["created_at"]
            else:
                element["date"] = 0
            branches.append(element)

        return branches

    def _stop_download(self, data):
        if self._current_tag is None:
            return False
        for entry in data:
            if ('name' in entry) and (self._current_tag == entry['name']):
                return True
        return False

    def get_tags(self, repository, current_tag=None, version_format=None) -> Optional[list]:
        # pylint: disable=unused-argument
        """ Returns a list of tags for this repository """
        uri = self._is_gitlab(repository)
        if uri is None:
            return None

        self._current_tag = current_tag
        tag_command = self.join_url(uri.scheme + '://', uri.netloc, 'api/v4/projects',
                                    self._project_name(uri),
                                    'repository/tags?order_by=updated&sort=desc')
        data = self._read_pages(tag_command)
        if data is None:
            return None
        tags = []
        for tag in data:
            tags.append({"name": tag['name'],
                         "date": datetime.datetime.fromisoformat(tag['commit']['committed_date'])})
        self._colors.clear_line()
        return tags


class Snapcraft(ProcessVersion):
    """ Implements all the YAML processing for snapcraft configuration files """
    def __init__(self, silent, github_pose=None, gitlab_pose=None):
        super().__init__(silent)
        self._secrets = {}
        self._config = None
        self._tag_error = False
        if github_pose:
            self._github = github_pose
        else:
            self._github = Github(silent)
        if gitlab_pose:
            self._gitlab = gitlab_pose
        else:
            self._gitlab = Gitlab(silent)

    def set_full_silent(self):
        super().set_full_silent()
        self._github.set_full_silent()
        self._gitlab.set_full_silent()

    def set_secret(self, backend, key, value):
        """ Sets an specific secret value for a backend """
        if backend == 'github':
            self._github.set_secret(key, value)
        elif backend == 'gitlab':
            self._gitlab.set_secret(key, value)
        else:
            print(f"Unknown backend: {backend}", file=sys.stderr)

    def load_local_file(self, filename=None):
        """ Given a path/filename, will load the corresponding SNAPCRAFT.YAML file """
        if filename is None:
            filename = '.'
        if os.path.isdir(filename):
            filename_tmp = os.path.join(filename, "snapcraft.yaml")
            if not os.path.exists(filename_tmp):
                filename_tmp = os.path.join(filename, "snap", "snapcraft.yaml")
                if not os.path.exists(filename_tmp):
                    print(f"No snapcraft file found at folder {filename}", file=sys.stderr)
            filename = filename_tmp
        if os.path.exists(filename):
            print(f"Opening file {filename}", file=sys.stderr)
            with open(filename, "r", encoding="utf8") as file_data:
                data = file_data.read()
            if self._open_yaml_file_with_extensions(data, "updatesnap"):
                self._check_extensions_are_right()
        self._load_secrets(filename)

    def load_external_data(self, data, secrets=None):
        """ process SNAPCRAFT.YAML data and SECRETS directly """

        self._load_secrets(None)
        if self._open_yaml_file_with_extensions(data, "updatesnap"):
            self._check_extensions_are_right()
        if secrets:
            self._secrets = yaml.safe_load(secrets)
            self._github.set_secrets(self._secrets)
            self._gitlab.set_secrets(self._secrets)

    def _check_extensions_are_right(self):
        for part_name in self._config["parts"]:
            part_data = self._config["parts"][part_name]
            if "version-format" not in part_data:
                continue
            if not isinstance(part_data["version-format"], dict):
                self._print_error(part_name, self._colors.critical, "The version-format data "
                                  "is not a dictionary. Ensure that the syntax is right "
                                  "(specifically, that any option is in the format "
                                  "'OptionName: true')")
                raise ValueError(f"The version-format data in {part_name} is not "
                                 "a dictionary.")

    def _open_yaml_file_with_extensions(self, data, ext_name):
        """ This method receives a YAML file content, explores it searching for a comment
            with the text '# ext:ext_name' (being 'ext_name' the parameter
            passed to the method), and it will include all the comments that
            follow it replacing the '#' with a blank space, until it finds
            another comment with the text '# endext', or with a non-comment
            line. This allows to add extra fields in a YAML file without
            breaking compatibility with snapcraft, because, by replacing
            the # with an space, the format is preserved.

            The 'ext_name' part allows to add in a file blocks for several
            different programs without they interferring with others. This
            way, program1 can enable only the blocks marked with '# ext:program1',
            while program2 can enable only the blocks marked with '# ext:program2',
            for example, thus allowing to just reuse this method."""

        newfile = ""
        replace_comments = False
        has_extensions = False
        for line in data.split("\n"):
            line += '\n'  # restore the newline at the end
            if line[0] != '#':
                newfile += line
                replace_comments = False
                continue
            # the line contains a valid comment
            if line == f'# ext:{ext_name}\n':
                has_extensions = True
                replace_comments = True
                continue
            if line == '# endext\n':
                replace_comments = False
                continue
            if replace_comments:
                line = line[1:]
                if (len(line) > 0) and (line[1] == ' '):
                    line = ' ' + line
                else:
                    line = '#' + line
            newfile += line
        if data[-1] != '\n' and newfile[-1] == '\n':
            newfile = newfile[:-1]
        self._config = yaml.safe_load(newfile)
        return has_extensions

    def _load_secrets(self, filename):
        secrets_file = os.path.expanduser('~/.config/updatesnap/updatesnap.secrets')
        if os.path.exists(secrets_file):
            with open(secrets_file, "r", encoding="utf8") as cfg:
                self._secrets = yaml.safe_load(cfg)
        else:
            if filename is not None:
                secrets_file = os.path.join(os.path.split(os.path.abspath(filename))[0],
                                            "updatesnap.secrets")
                if os.path.exists(secrets_file):
                    with open(secrets_file, "r", encoding="utf8") as cfg:
                        self._secrets = yaml.safe_load(cfg)
        self._github.set_secrets(self._secrets)
        self._gitlab.set_secrets(self._secrets)

    def _get_tags(self, source, current_tag=None, version_format=None):
        tags = self._github.get_tags(source, current_tag, version_format)
        if tags is not None:
            return tags
        tags = self._gitlab.get_tags(source, current_tag, version_format)
        return tags

    def _get_branches(self, source):
        branches = self._github.get_branches(source)
        if branches is not None:
            return branches
        branches = self._gitlab.get_branches(source)
        return branches

    def process_parts(self) -> tuple[list, bool]:
        """ Processes all the parts of the current YAML file

        It goes through each part in the current YAML file and
        updates the version to the latest one. """
        if self._config is None:
            return []
        self._tag_error = False
        parts = []
        for part in self._config['parts']:
            parts.append(self.process_part(part))
        return parts, self._tag_error

    def process_part(self, part: str) -> Optional[dict]:
        # pylint: disable=too-many-return-statements,too-many-branches,too-many-statements
        """ Processes an specific part of the current YAML file

        It takes the YAML data of the specified part, downloads all
        the tags from the github/gitlab of the source, compares them
        with the current version, finds the most recent in the repository,
        and returns the part data modified with the new version.

        If it returns None, there is no new version for that part
        """

        part_data = {
            "name": part,
            "version": None,
            "use_branch": False,
            "use_tag": False,
            "missing_format": False,
            "updates": [],
            "version_format": {},
            "source_url": None,
        }

        if self._config is None:
            return None

        if part not in self._config['parts']:
            return None

        data = self._config['parts'][part]

        if 'source' not in data:
            return None

        if data['source'].find("://") == -1:
            return None

        if 'source-tag' in data:
            current_tag = data['source-tag']
        else:
            current_tag = None

        version_format = data['version-format'] if ('version-format' in data) else {}

        if ('ignore' in version_format) and (version_format['ignore']):
            return None

        if ("format" not in version_format) and (current_tag is not None):
            # if the version format is not specified,
            # automagically detect it between any of these common formats:
            # * %M.%m.%R
            # * v%M.%m.%R
            # * %M.%m
            if re.match('^[0-9]+[.][0-9]+[.][0-9]+$', current_tag):
                version_format["format"] = '%M.%m.%R'
            elif re.match('^v[0-9]+[.][0-9]+[.][0-9]+$', current_tag):
                version_format["format"] = 'v%M.%m.%R'
            elif re.match('^[0-9]+[.][0-9]+$', current_tag):
                version_format["format"] = '%M.%m'
        part_data["version_format"] = version_format
        if "format" not in version_format:
            part_data['missing_format'] = True
        source = data['source']
        part_data["source_url"] = source

        if ((not source.startswith('http://')) and
            (not source.startswith('https://')) and
            (not source.startswith('git://')) and
                (('source-type' not in data) or (data['source-type'] != 'git'))):
            self._print_error(part, self._colors.critical, "Source is neither http:// nor git://",
                              source=source, extra_cr=True)
            return part_data

        if (not source.endswith('.git')) and (('source-type' not in data) or
                                              (data['source-type'] != 'git')):
            self._print_error(part, self._colors.warning, "Source is not a GIT repository",
                              source=source, extra_cr=True)
            return part_data

        if "source-depth" not in data:
            self._tag_error = True
            self._print_error(part, self._colors.critical, "No 'source-depth' entry",
                              source=source, extra_cr=True)
            return part_data

        if 'savannah' in source:
            url = urllib.parse.urlparse(source)
            if 'savannah' in url.netloc:
                self._print_error(part, self._colors.warning, "Savannah repositories not supported",
                                  source=source, extra_cr=True)
                return part_data

        self._print_message(part, None, source=source)

        if ('source-tag' not in data) and ('source-branch' not in data):
            try:
                tags = self._get_tags(source, current_tag, version_format)
                branches = self._get_branches(source)
            except (ValueError, ConnectionError) as exception:
                self._tag_error = True
                self._print_error(part, self._colors.critical, f"Invalid URI: {exception}",
                                  extra_cr=True)
                return part_data
            message = "Has neither a source-tag nor a source-branch element"
            if self._checkopt("allow-neither-tag-nor-branch", version_format):
                self._print_error(part, self._colors.warning, f"Warning: {message}",
                                  source=source, extra_cr=True)
            else:
                self._print_error(part, self._colors.critical, message, source=source,
                                  extra_cr=True)
                self._tag_error = True
            if tags is not None:
                self._print_last_tags(part, tags)

        if 'source-tag' in data:
            try:
                tags = self._get_tags(source, current_tag, version_format)
            except (ValueError, ConnectionError) as exception:
                self._tag_error = True
                self._print_error(part, self._colors.critical, f"Invalid URI: {exception}",
                                  extra_cr=True)
                return part_data
            part_data["use_tag"] = True
            self._print_message(part, f"Current tag: {data['source-tag']}\n", source=source)
            if tags is None:
                self._print_error(part, self._colors.critical, "No tags found. "
                                  "Ensure that the source URI is valid.", extra_cr=True)
                self._tag_error = True
                return part_data
            self._sort_tags(part, data['source-tag'], tags, part_data)

        if 'source-branch' in data:
            part_data["use_branch"] = True
            self._print_message(part, f"Current branch: {data['source-branch']}\n", source=source)
            current_version = data['source-branch']
            self._print_message(part, f"Current version: {current_version}\n")
            try:
                branches = self._get_branches(source)
            except (ValueError, ConnectionError) as exception:
                self._tag_error = True
                self._print_error(part, self._colors.critical, f"Invalid URI: {exception}",
                                  extra_cr=True)
                return part_data
            if branches is None:
                self._print_error(part, self._colors.critical, "No branches found. Ensure that "
                                  "the source URI is valid.", extra_cr=True)
                self._tag_error = True
                return part_data
            self._sort_elements(part, current_version, branches, "branch")
            self._print_last_branches(part, branches)
            message = "Uses branches. Should be moved to an specific tag"
            if self._checkopt("allow-branch", version_format):
                self._print_error(part, self._colors.warning, message, extra_cr=True)
            else:
                self._tag_error = True
                self._print_error(part, self._colors.critical, message, extra_cr=True)
        return part_data

    def _print_last_tags(self, part, tags):
        tags.sort(reverse=True, key=lambda x: x.get('date'))
        tags = tags[:4]
        self._print_message(part, "Last tags:\n")
        for tag in tags:
            self._print_message(part, f"  {tag['name']} ({tag['date']})\n")

    def _print_last_branches(self, part, branches):
        branches.sort(reverse=True, key=lambda x: x.get('date'))
        branches = branches[:4]
        self._print_message(part, "Last branches:\n")
        for branch in branches:
            self._print_message(part, f"  {branch['name']} ({branch['date']})\n")

    def _sort_tags(self, part, current_tag, tags, part_data):
        current_date = None
        found_tag = None
        for tag in tags:
            if tag['name'] == current_tag:
                current_date = tag['date']
                found_tag = tag
                break

        if current_date is None:
            self._print_error(part, self._colors.critical, f"Error:{self._colors.reset} "
                              "can't find the current tag in the tag list.")
            return

        version_format = part_data["version_format"]
        self._print_message(part, f"Current tag date: {current_date}\n")
        part_data['version'] = (found_tag['name'], current_date)
        current_version = self._get_version(part, current_tag, version_format, True)

        newer_tags = []
        for tag in tags:
            if tag['name'] == current_tag:
                continue

            if current_version is not None:
                version = self._get_version(part, tag['name'], version_format, False)
                if (version is None) or (version <= current_version):
                    continue

            if (current_version is None) and (tag['date'] < current_date):
                continue

            if (("same-major" in version_format) and
                    (version_format["same-major"]) and
                    (version.major != current_version.major)):
                continue

            if (("same-minor" in version_format) and
                    (version_format["same-minor"]) and
                    (version.minor != current_version.minor)):
                continue

            newer_tags.append(tag)

        if len(newer_tags) == 0:
            self._print_message(part, f"{self._colors.all_ok}Tag updated{self._colors.reset}\n")
            return

        self._print_message(part, f"{self._colors.warning}Newer tags:{self._colors.reset}\n")
        newer_tags.sort(reverse=True, key=lambda x: x.get('date'))
        for tag in newer_tags:
            self._print_message(part, f"  {tag['name']} ({tag['date']})\n")
            part_data["updates"].append(tag)

    def _sort_elements(self, part, current_version, elements, text):
        newer_elements = []
        if elements is None:
            elements = []
        current_element = None
        for element in elements:
            if current_version == element['name']:
                current_element = element
                break
        for element in elements:
            if ('date' in element) and ((current_element is None) or
                                        (element['date'] > current_element['date'])):
                newer_elements.append(element)
        if len(newer_elements) == 0:
            self._print_message(part, f"{self._colors.all_ok}Branch updated{self._colors.reset}\n")
        else:
            self._print_message(part, text)
            newer_elements.sort(reverse=True, key=lambda x: x.get('date'))
            for element in newer_elements:
                self._print_message(part, f"  {element}\n")

    def process_metadata(self) -> Optional[dict]:
        """ Returns metadata from Snapcraft.yaml file """
        metadata = {
            "name": None,
            "version": None,
            "adopt-info": None,
            "grade": None,
            "upstream-version": None,
            "upstream-url": None,
        }

        if self._config is None:
            return None
        data = self._config
        if 'name' in data:
            metadata['name'] = data['name']

        if 'version' in data:
            metadata['version'] = data['version']

        if 'adopt-info' in data:
            metadata['adopt-info'] = data['adopt-info']
            upstream_data = self.process_part(data['adopt-info'])
            metadata['upstream-url'] = upstream_data['source_url']
            if len(upstream_data['updates']) != 0:
                metadata['upstream-version'] = upstream_data['updates'][0]

        if 'grade' in data:
            metadata['grade'] = data['grade']
        return metadata
