#!/usr/bin/env python3

""" This program ensures that all the libraries in two SNAPs are ABI-compatible """

import sys
import os
import subprocess
import elftools.elf.elffile
import elftools.elf.sections

class Colors:
    #pylint: disable=too-few-public-methods
    """ Container class to define the colors for the messages """
    def __init__(self):
        red = "\033[31m"
        green = "\033[32m"
        yellow = "\033[33m"
        #cyan = "\033[36m"

        self.reset = "\033[0m"
        self.clearline = "\033[2K"

        self.color_missing_public_symbol = red
        self.color_new_public_symbol = green
        self.color_library = yellow

    def clear_line(self):
        """ Restore the colors to the default ones

        This must be called after showing a piece of text with any of
        the previous colors, to go back to the default color."""
        print(self.clearline, end="\r", file=sys.stderr)


def unmangle_symbol(symbol):
    """ Unmangles symbols to show in a more natural format the C++ methods """
    if symbol.startswith("_Z"):
        return subprocess.check_output(['c++filt', '-n', symbol]).decode('utf-8')[:-1]
    return symbol


class CompareABIs(Colors):
    """ Compares two libraries and determines if they are ABI-compatible """
    def __init__(self):
        super().__init__()
        self._old_library_path:str = None
        self._new_library_path:str = None
        self._old_library = None
        self._new_library = None
        self._old_library_symbols = {}
        self._new_library_symbols = {}


    def _process_file(self, path):
        # we need at least STT_FUNC
        symbols = {"STT_FUNC": []}
        with open(path, 'rb') as library:
            library_elf = elftools.elf.elffile.ELFFile(library)
            for section in library_elf.iter_sections():
                if isinstance(section, elftools.elf.sections.SymbolTableSection):
                    for symbol in section.iter_symbols():
                        symbol_type = symbol.entry.st_info.type
                        if symbol_type not in symbols:
                            symbols[symbol_type] = []
                        symbols[symbol_type].append(symbol)
        return library_elf, symbols


    def _load_library_files(self):
        #pylint: disable=broad-exception-raised
        """ Loads library files data (for old and new libraries) """

        if not os.path.isfile(self._old_library_path):
            raise Exception(f"The old library path {self._old_library_path} "
                             "doesn't point to a file")
        if not os.path.isfile(self._new_library_path):
            raise Exception(f"The new library path {self._new_library_path} "
                             "doesn't point to a file")

        self._old_library, self._old_library_symbols = self._process_file(self._old_library_path)
        self._new_library, self._new_library_symbols = self._process_file(self._new_library_path)


    def set_direct_paths(self, old_path: str, new_path: str):
        """ sets the paths of both libraries in an independent way. This
            is useful for testing. It can raise several exceptions if
            the paths are malformed or don't point to a library. """
        self._old_library_path = old_path
        self._new_library_path = new_path
        self._load_library_files()


    def set_snap_paths(self, base_old_path: str, base_new_path: str,
                           library_path: str):
        #pylint: disable=broad-exception-raised
        """ sets the paths of both libraries using the base paths for each SNAP,
            and the path of the library file inside the SNAPs. This
            presumes that both libraries are placed in the same relative place.
            If @library_path is relative, it will be joined to each snap path
            to generate the final paths; if it is absolute, it will be presumed
            that it's the path in the "old" snap, and the path in the "new"
            snap will be derived by replacing the old path with the new one.

            It can raise several exceptions if the paths are malformed or don't
            point to a library. """
        if library_path[0] == os.sep:
            if not library_path.startswith(base_old_path):
                raise Exception(f"Library path {library_path} isn't inside the"
                                f"old SNAP path {base_old_path}")
            self._old_library_path = library_path
            self._new_library_path = library_path.replace(base_old_path, base_new_path)
        else:
            self._old_library_path = os.path.join(base_old_path, library_path)
            self._new_library_path = os.path.join(base_new_path, library_path)
        self._load_library_files()


    def missing_symbols(self) -> bool:
        """ Compares the library pointed by new_path with the one pointed
            by base_path, and returns a boolean specifying if they are
            ABI-compatible """

        # Ensure that the new library has all the public symbols that the old
        # one exports

        compatible = True
        old_symbols = [ unmangle_symbol(symbol.name) for symbol in
                        self._old_library_symbols["STT_FUNC"] ]
        new_symbols = [ unmangle_symbol(symbol.name) for symbol in
                        self._new_library_symbols["STT_FUNC"] ]
        for symbol in old_symbols:
            if symbol not in new_symbols:
                compatible = False
                print(f"Missing public symbol {self.color_missing_public_symbol}{symbol}"
                      f"{self.reset} in {self.color_library}{self._new_library_path}"
                      f"{self.reset}", file=sys.stderr)
        return compatible


    def new_symbols(self):
        """ Compares the library pointed by new_path with the one pointed
            by base_path, and lists all the new symbols """

        old_symbols = [ unmangle_symbol(symbol.name) for symbol in
                        self._old_library_symbols["STT_FUNC"] ]
        new_symbols = [ unmangle_symbol(symbol.name) for symbol in
                        self._new_library_symbols["STT_FUNC"] ]
        for symbol in new_symbols:
            if symbol not in old_symbols:
                print(f"New public symbol {self.color_new_public_symbol}{symbol}"
                      f"{self.reset} in {self.color_library}{self._new_library_path}"
                      f"{self.reset}")


class SnapComparer(Colors):
    """ Compares two snaps to find ABI breaks """

    def __init__(self):
        super().__init__()
        self._path_pairs = []

    def _resolve_link(self, path: str) -> str:
        """ given a path, if it is a symlink, will resolve recursively
            until obtaining the final file. """
        while os.path.islink(path):
            newpath = os.readlink(path)
            if newpath[0] != os.sep:
                newpath = os.path.join(os.path.dirname(path), newpath)
            path = newpath
        return path

    def _should_check(self, path1: str, path2: str) -> bool:
        """ Returns True if the files contents are different and
            both are ELF files.
            Returns False if both files contents are the same, or
            any of the files doesn't exist, or any of them aren't an
            ELF file """

        path1 = self._resolve_link(path1)
        path2 = self._resolve_link(path2)

        if (path1, path2) in self._path_pairs:
            # already checked that pair
            return False

        self._path_pairs.append((path1, path2))

        if not os.path.isfile(path1) or not os.path.isfile(path2):
            return False

        elf_signature = bytearray([0x7F, 0x45, 0x4C, 0x46])
        with open(path1, 'rb') as old_library:
            with open(path2, 'rb') as new_library:
                if ((old_library.read(4) != elf_signature) or
                    (new_library.read(4) != elf_signature)):
                    return False
                if os.stat(path1).st_size == os.stat(path2).st_size:
                    while True:
                        data_old = old_library.read(4096)
                        data_new = new_library.read(4096)
                        if data_old != data_new:
                            return True
                        if data_old == b'': # EOF
                            return False
        return True


    def compare_snaps(self, old_snap_path, new_snap_path, show_new_symbols):
        # pylint: disable=bare-except
        """ Does the comparison between the libraries of old_snap_path
            and new_snap_path. """
        base_paths = ["lib", "usr/lib32", "usr/lib64", "usr/lib"]

        for lpath in base_paths:
            old_path = os.path.join(old_snap_path, lpath)
            new_path = os.path.join(new_snap_path, lpath)
            for root, _, files in os.walk(old_path):
                for filename in files:
                    full_old_path = os.path.join(root, filename)
                    full_new_path = full_old_path.replace(old_path, new_path)
                    if not self._should_check(full_old_path, full_new_path):
                        continue
                    compare = CompareABIs()
                    try:
                        compare.set_direct_paths(full_old_path, full_new_path)
                    except:
                        continue
                    if show_new_symbols:
                        compare.new_symbols()
                    else:
                        compare.missing_symbols()


def usage():
    """ Prints how to use the program """
    print("Usage: abi_breaker [--new] OLD_SNAP_PATH NEW_SNAP_PATH")
    sys.exit(1)

def _do_process():
    old_snap_path = None
    new_snap_path = None
    check_for_new = False

    for parameter in sys.argv[1:]:
        if parameter[0] == '-':
            if parameter == '--new':
                check_for_new = True
                continue
            print(f"Unknown parameter {parameter}")
            usage()
        if old_snap_path is None:
            old_snap_path = parameter
            continue
        if new_snap_path is None:
            new_snap_path = parameter
            continue
        print("Too many parameters")
        usage()

    if (old_snap_path is None) or (new_snap_path is None):
        usage()

    comparer = SnapComparer()
    comparer.compare_snaps(old_snap_path, new_snap_path, check_for_new)

if __name__ == '__main__':
    _do_process()
