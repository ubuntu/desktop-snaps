#!/usr/bin/env python3

""" Unitary tests for abi_breaker """

import unittest
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


unittest.main()
