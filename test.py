import unittest

import _test
import numpy as np
from numpy.random import random
from numpy.testing import assert_array_equal

from futhark_ffi import Futhark
from futhark_ffi.compat import FutharkCompat


class TestFFI(unittest.TestCase):
    def setUp(self):
        self.fut = Futhark(_test)

    def test_int(self):
        self.assertEqual(self.fut.test1(5), 6)

    def test_list_input(self):
        data = np.arange(10)
        self.assertEqual(self.fut.test2(data), np.sum(data))

    def test_list_output(self):
        data = np.arange(10)
        res = self.fut.test3(data)
        pyres = self.fut.from_futhark(res)
        assert_array_equal(pyres, np.cumsum(data))

    def test_multi_output(self):
        self.assertEqual(self.fut.test4(4,5), (4+5, 4-5))

    def test_2d(self):
        data = np.arange(9).reshape(3,3)

        res = self.fut.test5(data)
        pyres = self.fut.from_futhark(res)
        assert_array_equal(pyres, data*2)

        res = self.fut.test5(data.T)
        pyres = self.fut.from_futhark(res)
        assert_array_equal(pyres, (data*2).T)

    def test_opaque(self):
        res = self.fut.test6(10)
        (pos, neg) = self.fut.test7(res)
        (pos, neg) = self.fut.from_futhark(pos, neg)
        assert_array_equal(pos, np.arange(10))
        assert_array_equal(neg, -np.arange(10))

    def test_bool(self):
        res = self.fut.test8(True)
        self.assertEqual(res, False)

    def test_error(self):
        with self.assertRaises(ValueError):
            self.fut.test9(np.arange(4))

class TestCompat(unittest.TestCase):
    def setUp(self):
        self.fut = FutharkCompat(_test)

    def test_int(self):
        self.assertEqual(self.fut.test1(5), 6)

    def test_list_input(self):
        data = np.arange(10)
        self.assertEqual(self.fut.test2(data), np.sum(data))

    def test_list_output(self):
        data = np.arange(10)
        res = self.fut.test3(data).get()
        assert_array_equal(res, np.cumsum(data))

    def test_multi_output(self):
        self.assertEqual(self.fut.test4(4,5), (4+5, 4-5))

    def test_2d(self):
        data = np.arange(9).reshape(3,3)

        res = self.fut.test5(data).get()
        assert_array_equal(res, data*2)

        res = self.fut.test5(data.T).get()
        assert_array_equal(res, (data*2).T)

    def test_opaque(self):
        res = self.fut.test6(10)
        (pos, neg) = self.fut.test7(res)
        assert_array_equal(pos.get(), np.arange(10))
        assert_array_equal(neg.get(), -np.arange(10))

    def test_bool(self):
        res = self.fut.test8(True)
        self.assertEqual(res, False)

    def test_error(self):
        with self.assertRaises(ValueError):
            self.fut.test9(np.arange(4))

if __name__ == '__main__':
    unittest.main()
