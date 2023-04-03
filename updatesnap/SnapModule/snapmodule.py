import requests
import yaml
import urllib
import re
import time
import os
import datetime

import pkg_resources

class Colors(object):
    def __init__(self):
        self.red = "\033[31m"
        self.green = "\033[32m"
        self.yellow = "\033[33m"
        self.cyan = "\033[36m"
        self.reset = "\033[0m"

        self.critical = self.red
        self.warning = self.yellow
        self.ok = self.green
        self.note = self.cyan


    def clear_line(self):
        print("\033[2K", end="\r") # clear the line

class ProcessVersion(object):

    def _read_number(self, text):
        n = 0
        if (len(text) == 0) or (text[0] not in '0123456789'):
            return None, text
        while (len(text) > 0) and (text[0] in '0123456789'):
            n *= 10
            n += int(text[0])
            text = text[1:]
        return n, text


    def _get_version(self, part, entry, entry_format, check):
        if "format" not in entry_format:
            if check:
                self._print_message(part, f"{self._colors.critical}Missing tag version format for {part}{self._colors.reset}.")
            return None # unknown format
        major = 0
        minor = 0
        revision = 0
        # space is "no element". Adding it in front of the first block simplifies the code
        fmt = (" " + entry_format["format"]).split("%")
        for part in fmt:
            if part[0] != ' ':
                number, entry = self._read_number(entry)
                if number is None:
                    return None # not found a number when expected
                if part[0] == 'M':
                    major = number
                elif part[0] == 'm':
                    minor = number
                elif part[0] == 'R':
                    revision = number
            part = part[1:]
            if len(part) == 0:
                continue
            if not entry.startswith(part):
                return None
            entry = entry[len(part):]
        version = pkg_resources.parse_version(f"{major}.{minor}.{revision}")
        if "lower-than" in entry_format:
            if version >= pkg_resources.parse_version(str(entry_format["lower-than"])):
                return None
        if ("ignore-odd-minor" in entry_format) and (entry_format["ignore-odd-minor"]):
            if (minor % 2) == 1:
                return None
        if ("no-9x-revisions" in entry_format) and (entry_format["no-9x-revisions"]):
            if revision >= 90:
                return None

        return version


class GitClass(ProcessVersion):
    def __init__(self, repo_type, silent = False):
        super().__init__()
        self._silent = silent
        self._token = None
        self._user = None
        self._colors = Colors()
        self._repo_type = repo_type
        self._current_tag = None


    def set_secrets(self, secrets):
        if (self._repo_type == 'github') and 'github' in secrets:
            self._user = secrets['github']['user']
            self._token = secrets['github']['token']


    def set_secret(self, secret, value):
        if secret == 'user':
            self._user = value
        elif secret == 'token':
            self._token = value


    def _read_uri(self, uri):
        if not self._silent:
            print(f"Asking URI {uri}     ", end="\r")
        while True:
            try:
                if (self._user is not None) and (self._token is not None):
                    response = requests.get(uri, auth=requests.auth.HTTPBasicAuth(self._user, self._token))
                else:
                    response = requests.get(uri)
                break
            except:
                if not self._silent:
                    print(f"Retrying URI {uri}     ", end="\r")
                time.sleep(1)
        return response

    def _stop_download(self, data):
        return False

    def _read_pages(self, uri):
        elements = []
        while uri is not None:
            response = self._read_uri(uri)
            if response.status_code != 200:
                if not self._silent:
                    print(f"{self._colors.critical}Status code {response.status_code} when asking for {uri}{self._colors.reset}")
                return []
            headers = response.headers
            data = response.json()
            for entry in data:
                elements.append(entry)
            if self._stop_download(data):
                break
            uri = None
            if "Link" in headers:
                l = headers["link"]
                entries = l.split(",")
                for e in entries:
                    if 'rel="next"' not in e:
                        continue
                    p1 = e.find("<")
                    p2 = e.find(">")
                    uri = e[p1+1:p2]
                    break
        self._colors.clear_line()
        return elements


    def _read_page(self, uri):
        response = self._read_uri(uri)
        if response.status_code != 200:
            print(f"{self._colors.critical}Status code {response.status_code} when asking for {uri}{self._colors.reset}")
            return None
        headers = response.headers
        data = response.json()
        return data


    def _get_uri(self, repository, min_elements):
        repository = repository.strip()
        if repository[-4:] == '.git':
            repository = repository[:-4]
        uri = urllib.parse.urlparse(repository)
        elements = uri.path.split("/")
        if (uri.scheme != 'http') and (uri.scheme != 'https') and (uri.scheme != 'git'):
            print(f"{self._colors.critical}Unrecognized protocol in repository {repository}{self._colors.reset}")
            return None
        elements = uri.path.split("/")
        if len(elements) < min_elements:
            print(f"{self._colors.critical}Invalid uri format for repository {repository}{self._colors.reset}")
            return None
        return uri


    def _rb(self, text):
        """ Remove trailing and heading '/' characters, to simplify building URIs """
        while (len(text) > 0) and (text[0] == '/'):
            text = text[1:]
        while (len(text) > 0) and (text[-1] == '/'):
            text = text[:-1]
        return text


    def join_url(self, *args):
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
    def __init__(self, silent = False):
        super().__init__("github", silent)
        self._api_url = 'https://api.github.com/repos/'


    def _is_github(self, repository):
        uri = self._get_uri(repository, 3)
        if uri is None:
            return None
        if (uri.netloc != "github.com") and (uri.netloc != "www.github.com"):
            return None
        return uri


    def get_branches(self, repository):
        uri = self._is_github(repository)
        if uri is None:
            return None

        branch_command = self.join_url(self._api_url, uri.path, 'branches')
        return self._read_pages(branch_command)


    def _stop_download(self, data):
        if self._current_tag is None:
            return False
        for entry in data:
            if ('name' in entry) and (self._current_tag == entry['name']):
                return True
        return False


    def get_tags(self, repository, current_tag = None, version_format = {}):
        uri = self._is_github(repository)
        if uri is None:
            return None

        self._current_tag = current_tag
        tag_command = self.join_url(self._rb(self._api_url), self._rb(uri.path), 'tags?sort=created&direction=desc')
        data = self._read_pages(tag_command)
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
        self._colors.clear_line()
        return tags


    def get_file(self, repository, file_path):
        uri = self._is_github(repository)
        if uri is None:
            return None

        tag_command = self.join_url(self._rb(self._api_url), self._rb(uri.path), 'contents', file_path)
        data = self._read_page(tag_command)
        return data


class Gitlab(GitClass):
    def __init__(self, silent = False):
        super().__init__("gitlab", silent)


    def _is_gitlab(self, repository):
        uri = self._get_uri(repository, 3)
        if uri is None:
            return None
        if "gitlab" not in uri.netloc:
            return None
        return uri


    def _project_name(self, uri):
        name = uri.path
        while name[0] == '/':
            name = name[1:]
        return name.replace('/', '%2F')


    def get_branches(self, repository):
        uri = self._is_gitlab(repository)
        if uri is None:
            return None

        branch_command = self.join_url(uri.scheme + '://', uri.netloc, 'api/v4/projects', self._project_name(uri), 'repository/branches')
        data = self._read_pages(branch_command)
        branches = []
        for branch in data:
            branches.append({"name": branch['name']})
        return branches


    def _stop_download(self, data):
        if self._current_tag is None:
            return False
        for entry in data:
            if ('name' in entry) and (self._current_tag == entry['name']):
                return True
        return False


    def get_tags(self, repository, current_tag = None, version_format = {}):
        uri = self._is_gitlab(repository)
        if uri is None:
            return None

        self._current_tag = current_tag
        tag_command = self.join_url(uri.scheme + '://', uri.netloc, 'api/v4/projects', self._project_name(uri), 'repository/tags?order_by=updated&sort=desc')
        data = self._read_pages(tag_command)
        tags = []
        for tag in data:
            tags.append({"name": tag['name'],
                         "date": datetime.datetime.fromisoformat(tag['commit']['committed_date'])})
        self._colors.clear_line()
        return tags


class Snapcraft(ProcessVersion):
    def __init__(self, silent):
        super().__init__()
        self._colors = Colors()
        self._secrets = {}
        self._config = None
        self.silent = silent
        self._last_part = None
        self._github = Github(silent)
        self._gitlab = Gitlab(silent)


    def set_secret(self, backend, key, value):
        if backend == 'github':
            self._github.set_secret(key, value)
        elif backend == 'gitlab':
            self._gitlab.set_secret(key, value)
        else:
            print(f"Unknown backend: {backend}")


    def load_local_file(self, filename = None):
        """ Given a path/filename, will load the corresponding SNAPCRAFT.YAML file """
        if filename is None:
            filename = '.'
        if os.path.isdir(filename):
            f1 = os.path.join(filename, "snapcraft.yaml")
            if not os.path.exists(f1):
                f1 = os.path.join(filename, "snap", "snapcraft.yaml")
                if not os.path.exists(f1):
                    print(f"No snapcraft file found at folder {filename}")
            filename = f1
        if os.path.exists(filename):
            print(f"Opening file {filename}")
            with open(filename, "r") as f:
                data = f.read()
            self._open_yaml_file_with_extensions(data, "updatesnap")
        self._load_secrets(filename)


    def load_external_data(self, data, secrets = None):
        """ process SNAPCRAFT.YAML data and SECRETS directly """

        self._load_secrets(None)
        self._open_yaml_file_with_extensions(data, "updatesnap")
        if secrets:
            self._secrets = yaml.safe_load(secrets)
            self._github.set_secrets(self._secrets)
            self._gitlab.set_secrets(self._secrets)


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
        for l in data.split("\n"):
            l += '\n' # restore the newline at the end
            if (len(l) == 0) or (l[0] != '#'):
                newfile += l
                replace_comments = False
                continue
            # the line contains a valid comment
            if l == f'# ext:{ext_name}\n':
                replace_comments = True
                continue
            if l == '# endext\n':
                replace_comments = False
                continue
            if replace_comments:
                l = l[1:]
                if (len(l) > 0) and (l[1] == ' '):
                    l = ' ' + l
            newfile += l
        self._config = yaml.safe_load(newfile)


    def _load_secrets(self, filename):
        secrets_file = os.path.expanduser('~/.config/updatesnap/updatesnap.secrets')
        if os.path.exists(secrets_file):
            with open(secrets_file, "r") as cfg:
                self._secrets = yaml.safe_load(cfg)
        else:
            if filename is not None:
                secrets_file = os.path.join(os.path.split(os.path.abspath(filename))[0], "updatesnap.secrets")
                if os.path.exists(secrets_file):
                    with open(secrets_file, "r") as cfg:
                        self._secrets = yaml.safe_load(cfg)
        self._github.set_secrets(self._secrets)
        self._gitlab.set_secrets(self._secrets)


    def _print_message(self, part, message, source = None):
        if self.silent:
            return
        if part != self._last_part:
            print(f"Part: {self._colors.note}{part}{self._colors.reset}{f' ({source})' if source else ''}")
            self._last_part = part
        if message is not None:
            print("  " + message, end="")
            print(self._colors.reset)


    def _get_tags(self, source, current_tag = None, version_format = {}):
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


    def process_parts(self):
        if self._config is None:
            return []
        parts = []
        for part in self._config['parts']:
            parts.append(self.process_part(part))
        return parts


    def process_part(self, part):
        part_data = {
            "name": part,
            "version": None,
            "use_branch": False,
            "use_tag": False,
            "missing_format": False,
            "updates": []
        }
        if self._config is None:
            return None
        if part not in self._config['parts']:
            return None
        data = self._config['parts'][part]
        if 'source' not in data:
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
        source = data['source']

        if ((not source.startswith('http://')) and
            (not source.startswith('https://')) and
            (not source.startswith('git://')) and
            ((not 'source-type' in data) or (data['source-type'] != 'git'))):
                self._print_message(part, f"{self._colors.critical}Source is neither http:// nor git://{self._colors.reset}", source = source)
                print()
                return part_data

        if (not source.endswith('.git')) and ((not 'source-type' in data) or (data['source-type'] != 'git')):
            self._print_message(part, f"{self._colors.warning}Source is not a GIT repository{self._colors.reset}", source = source)
            print()
            return part_data

        if 'savannah' in source:
            url = urllib.parse.urlparse(source)
            if 'savannah' in url.netloc:
                self._print_message(part, f"{self._colors.warning}Savannah repositories not supported{self._colors.reset}", source = source)
                if not self.silent:
                    print()
                return part_data

        self._print_message(part, None, source = source)
        tags = self._get_tags(source, current_tag, version_format)

        if ('source-tag' not in data) and ('source-branch' not in data):
            self._print_message(part, f"{self._colors.warning}Has neither a source-tag nor a source-branch{self._colors.reset}", source = source)
            self._print_last_tags(part, tags)

        if 'source-tag' in data:
            part_data["use_tag"] = True
            self._print_message(part, f"Current tag: {data['source-tag']}", source = source)
            self._sort_tags(part, data['source-tag'], tags, version_format, part_data)

        if 'source-branch' in data:
            part_data["use_branch"] = True
            self._print_message(part, f"Current branch: {data['source-branch']}", source = source)
            current_version = data['source-branch']
            self._print_message(part, f"Current version: {current_version}")
            branches = self._get_branches(source)
            self._sort_elements(part, current_version, branches, "branch")
            self._print_message(part, f"{self._colors.note}Should be moved to an specific tag{self._colors.reset}")
            self._print_last_tags(part, tags)
        if not self.silent:
            print()
        return part_data


    def _print_last_tags(self, part, tags):
        tags.sort(reverse = True, key=lambda x: x.get('date'))
        tags = tags[:4]
        self._print_message(part, f"Last tags:")
        for tag in tags:
            self._print_message(part, f"  {tag['name']} ({tag['date']})")


    def _sort_tags(self, part, current_tag, tags, version_format, part_data):
        if tags is None:
            self._print_message(part, f"{self._colors.critical}No tags found")
            return

        if "format" not in version_format:
            part_data['missing_format'] = True
        current_date = None
        for tag in tags:
            if tag['name'] == current_tag:
                current_date = tag['date']
                break
        if current_date is None:
            self._print_message(part, f"{self._colors.critical}Error:{self._colors.reset} can't find the current tag in the tag list.")
            return
        self._print_message(part, f"Current tag date: {current_date}")
        part_data['version'] = (tag['name'], current_date)
        current_version = self._get_version(part, current_tag, version_format, True)
        newer_tags = []
        for t in tags:
            if t['name'] == current_tag:
                continue
            if t['date'] < current_date:
                continue
            if current_version is not None:
                version = self._get_version(part, t['name'], version_format, False)
                if version is None:
                    continue
                if version < current_version:
                    continue
            if ("same-major" in version_format) and (version_format["same-major"]):
                if version.major != current_version.major:
                    continue
            if ("same-minor" in version_format) and (version_format["same-minor"]):
                if version.minor != current_version.minor:
                    continue
            newer_tags.append(t)

        if len(newer_tags) == 0:
            self._print_message(part, f"{self._colors.ok}Tag updated{self._colors.reset}")
        else:
            self._print_message(part, f"{self._colors.warning}Newer tags:{self._colors.reset}")
            newer_tags.sort(reverse = True, key=lambda x: x.get('date'))
            for tag in newer_tags:
                self._print_message(part, f"  {tag['name']} ({tag['date']})")
                part_data["updates"].append(tag)


    def _sort_elements(self, part, current_version, elements, text, show_equal = False):
        newer_elements = []
        if elements is None:
            elements = []
        current_element = None
        for element in elements:
            if current_version == element['name']:
                current_element = element
                break
        for element in elements:
            if (current_element is None) or (('date' in element) and (element['date'] > current_element['date'])):
                newer_elements.append(element)
        if len(newer_elements) == 0:
            self._print_message(part, f"{self._colors.ok}Branch updated{self._colors.reset}")
        else:
            self._print_message(part, text)
            newer_elements.sort(reverse = True, key=lambda x: x.get('date'))
            for element in newer_elements:
                self._print_message(part, "  " + element)
