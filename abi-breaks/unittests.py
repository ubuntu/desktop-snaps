#!/usr/bin/env python3

""" Unitary tests for abi_breaker """

import os
import tempfile
import unittest
from unittest import mock
import abi_breaker


class TestBreakerfiles(unittest.TestCase):
    """ Unitary tests for abi_breaker """

    def test_is_compatible(self):
        """ tests if two libraries are detected as compatible """
        comparer = abi_breaker.CompareABIs()
        comparer.set_direct_paths('tests/libtest.so.1.1', 'tests/libtest.so.1.2')
        symbols = comparer.missing_symbols()
        assert len(symbols) == 0

    def test_is_incompatible1(self):
        """ tests if two libraries are detected as incompatible when a function is missing"""
        comparer = abi_breaker.CompareABIs()
        comparer.set_direct_paths('tests/libtest.so.1.1', 'tests/libtest.so.1.3')
        symbols = comparer.missing_symbols()
        assert len(symbols) == 1
        assert symbols[0] == 'function1'

    def test_is_incompatible2(self):
        """ tests if two libraries are detected as incompatible when a global variable is missing"""
        comparer = abi_breaker.CompareABIs()
        comparer.set_direct_paths('tests/libtest.so.1.1', 'tests/libtest.so.1.4')
        symbols = comparer.missing_symbols()
        assert len(symbols) == 1
        assert symbols[0] == 'variable_one'

    def test_path_doesnt_exist(self):
        """ tests that the module doesn't break if a file doesn't exist """
        comparer = abi_breaker.CompareABIs()
        self.assertRaises(ValueError, comparer.set_direct_paths,
                          'tests/libtest.so.1.1', 'tests/libtest_doesn_t_exist.so.1.4')
        self.assertRaises(ValueError, comparer.set_direct_paths,
                          'tests/libtest_doesn_t_exist.so.1.1', 'tests/libtest.so.1.4')
        self.assertRaises(ValueError, comparer.set_direct_paths,
                          'tests/libtest_doesn_t_exist.so.1.1',
                          'tests/libtest_doesn_t_exist.so.1.4')

    def test_compare_snaps_path_mapping(self):
        """ tests that new paths are built relative to the search root, even
            when the root path appears again inside the library path """
        with tempfile.TemporaryDirectory() as tmpdir:
            old_snap = os.path.join(tmpdir, 'snap')
            new_snap = os.path.join(tmpdir, 'new')
            nested_dir = os.path.join(old_snap, 'lib', tmpdir.lstrip(os.sep), 'snap', 'lib')
            os.makedirs(nested_dir)
            with open(os.path.join(nested_dir, 'libx.so'), 'w', encoding='utf-8'):
                pass

            comparer = abi_breaker.SnapComparer()
            with mock.patch.object(comparer, '_should_check', return_value=False) as should_check:
                comparer.compare_snaps(old_snap, new_snap, False)

            rel_path = os.path.join(tmpdir.lstrip(os.sep), 'snap', 'lib', 'libx.so')
            should_check.assert_called_once_with(os.path.join(old_snap, 'lib', rel_path),
                                                 os.path.join(new_snap, 'lib', rel_path))


unittest.main()
