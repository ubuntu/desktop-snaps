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
        """ tests if two libraries are detected as incompatible """
        comparer = abi_breaker.CompareABIs()
        comparer.set_direct_paths('tests/libtest.so.1.1', 'tests/libtest.so.1.3')
        symbols = comparer.missing_symbols()
        assert len(symbols) == 1
        assert symbols[0] == 'function1'

unittest.main()
