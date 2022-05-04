from typing import Iterable

import numpy as np


__all__ = ['BitVector']


class BitVector(object):
    """
    Class for bitwise operations on an array as
    a large single value.

    The vector contains values in the numpy array, where
    it stores each bit in unsigned 8-bit integer values.

    Parameters
    ----------
    bit_count: int
        length of the vector in bits (count of valid
        bits in the vector).

    Raises
    ------
    ValueError
        if bit_count is less than 1.
    """

    BITS_IN_VALUE = 8

    def __init__(self, bit_count: int):
        if bit_count < 1:
            raise ValueError(
                'The number of bits cannot be less than 1, '
                'got %d' % bit_count)

        self._vals_c = bit_count // self.BITS_IN_VALUE
        if bit_count % self.BITS_IN_VALUE:
            self._vals_c += 1
        self._bit_c = bit_count
        self._vals = np.zeros(self._vals_c, dtype=np.uint8)

    def get_bit(self, index: int) -> int:
        """Get the bit value by index"""
        if index >= self._bit_c or index < -self._bit_c:
            raise IndexError('bit index out of range')
        i_val, i_bit = np.divmod(index, self.BITS_IN_VALUE)
        return (self._vals[-i_val - 1] & 1 << i_bit) >> i_bit

    def get_flag(self, index: int) -> bool:
        """Get the bit flag by index"""
        return bool(self.get_bit(index))

    @property
    def values(self) -> np.ndarray:
        """Array of the values in the vector."""
        return self._vals

    @values.setter
    def values(self, new_values: np.ndarray | Iterable | int):
        """Set new values to the vector."""
        values = np.array(new_values, dtype=np.uint8)
        if values.shape != self._vals.shape:
            raise ValueError(
                'Invalid shape of the new values: '
                f'{values.shape} != {self._vals.shape}')
        bits_mod = self._bit_c % self.BITS_IN_VALUE
        if bits_mod:
            values[0] &= 0xff >> self.BITS_IN_VALUE - bits_mod
        self._vals = values

    @property
    def bit_count(self) -> int:
        """Length of the vector in bits."""
        return self._bit_c

    @bit_count.setter
    def bit_count(self, count: int):
        """Set new bit count in the vector"""
        if count < 1:
            raise ValueError(
                'The number of bits cannot be less than 1, '
                'got %d' % count)

        vals_c = count // self.BITS_IN_VALUE
        vals_c_mod = count % self.BITS_IN_VALUE
        if vals_c_mod:
            vals_c += 1

        vals_diff = vals_c - self._vals_c
        if vals_diff > 0:
            self._vals = np.hstack(
                ([0] * vals_diff, self._vals))
        elif vals_diff <= 0:
            self._vals = self._vals[np.abs(vals_diff):]
            if vals_c_mod:
                self._vals[0] &= \
                    0xff >> self.BITS_IN_VALUE - vals_c_mod
        self._bit_c = count
        self._vals_c = vals_c