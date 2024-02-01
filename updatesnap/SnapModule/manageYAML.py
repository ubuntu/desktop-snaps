from typing import Optional

class ManageYAML:
    """ This class takes a YAML file and splits it in an array with each
        block, preserving the child structure to allow to re-create it without
        loosing any line. This can't be done by reading it with the YAML module
        because it deletes things like comments. """
    def __init__(self, yaml_data: str):
        self._original_data = yaml_data
        self._tree = self._split_yaml(yaml_data.split('\n'))[1]

    def _split_yaml(self, contents: str, level: int = 0, clevel: int = 0,
                    separator: str = ' ') -> tuple[list, str]:
        """ Transform a YAML text file into a tree

        Splits a YAML file in lines in a format that preserves the structure,
        the order and the comments. """

        data = []
        while len(contents) != 0:
            if len(contents[0].lstrip()) == 0 or contents[0][0] == '#':
                if data[-1]['child'] is None:
                    data[-1]['child'] = []
                data[-1]['child'].append({'separator': '',
                                          'data': contents[0].lstrip(),
                                          'child': None,
                                          'level': clevel + 1})
                contents = contents[1:]
                continue
            if not contents[0].startswith(separator * level):
                return contents, data
            if level == 0:
                if contents[0][0] == ' ' or contents[0][0] == '\t':
                    separator = contents[0][0]
            if contents[0][level] != separator:
                data.append({'separator': separator * level,
                             'data': contents[0].lstrip(),
                             'child': None,
                             'level': clevel})
                contents = contents[1:]
                continue
            old_level = level
            while contents[0][level] == separator:
                level += 1
            contents, inner_data = self._split_yaml(contents, level, clevel+1, separator)
            level = old_level
            if data[-1]['child'] is None:
                data[-1]['child'] = inner_data
            else:
                data[-1]['child'] += inner_data
        return [], data

    def get_part_data(self, part_name: str) -> Optional[dict]:
        """ Returns all the entries of an specific part of the current
            YAML file. For example, the 'glib' part from a YAML file
            with several parts. It returns None if that part doesn't
            exist """

        for entry in self._tree:
            if entry['data'] != 'parts:':
                continue
            if ('child' not in entry) or (entry['child'] is None):
                continue
            for entry2 in entry['child']:
                if entry2['data'] != f'{part_name}:':
                    continue
                return entry2['child']
        return None

    def get_part_element(self, part_name: str, element: str) -> Optional[dict]:
        """ Returns an specific entry for an specific part in the YAML file.
            For example, it can returns the 'source-tag' entry of the part
            'glib' from a YAML file with several parts. """

        part_data = self.get_part_data(part_name)
        if part_data:
            for entry in part_data:
                if entry['data'].startswith(element):
                    return entry
        return None

    def _get_yaml_group(self, group):
        data = ""
        for entry in group:
            data += entry['separator']
            data += entry['data']
            data += '\n'
            if entry['child']:
                data += self._get_yaml_group(entry['child'])
        return data

    def get_yaml(self) -> str:
        """ Returns the YAML file updated with the new versions """
        data = self._get_yaml_group(self._tree)
        data = data.rstrip()
        if data[-1] != '\n':
            data += '\n'
        return data
    
    def get_metadata(self) -> Optional[dict]:
        """ Returns metadata in form of list """
        data = []
        for entry in self._tree:
            if entry['data'] == 'part':
                continue
            data.append(entry)
        return data

    def get_part_metadata(self, element: str) -> Optional[dict]:
        """ Returns specific element of the metadata"""
        metadata = self.get_metadata()
        if metadata:
            for entry in metadata:
                if entry['data'].startswith(element):
                    return entry
        return None
