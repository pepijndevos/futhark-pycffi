import unittest
import numpy as np
from numpy.random import random
from numpy.testing import assert_array_equal
import _test
from futhark_ffi import Futhark

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
        assert_array_equal(self.fut.test3(data), np.cumsum(data))

    def test_multi_output(self):
        self.assertEqual(self.fut.test4(4,5), (4+5, 4-5))

    def test_2d(self):
        data = np.arange(9).reshape(3,3)
        assert_array_equal(self.fut.test5(data), data*2)
        with self.assertRaises(ValueError):
            self.fut.test5(data.T)

if __name__ == '__main__':
    unittest.main()
