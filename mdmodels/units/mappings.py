#  -----------------------------------------------------------------------------
#   Copyright (c) 2024 Jan Range
#
#   Permission is hereby granted, free of charge, to any person obtaining a copy
#   of this software and associated documentation files (the "Software"), to deal
#   in the Software without restriction, including without limitation the rights
#   to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#   copies of the Software, and to permit persons to whom the Software is
#   furnished to do so, subject to the following conditions:
#  #
#   The above copyright notice and this permission notice shall be included in
#   all copies or substantial portions of the Software.
#  #
#   THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#   IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#   FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#   AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#   LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#   OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
#   THE SOFTWARE.
#  -----------------------------------------------------------------------------
from .unit_definition import UnitType

UNIT_MAPPING = {
    "s": UnitType.SECOND,
    "m": UnitType.METRE,
    "kg": UnitType.KILOGRAM,
    "g": UnitType.GRAM,
    "mol": UnitType.MOLE,
    "K": UnitType.KELVIN,
    "A": UnitType.AMPERE,
    "cd": UnitType.CANDELA,
    "rad": UnitType.RADIAN,
    "sr": UnitType.STERADIAN,
    "Hz": UnitType.HERTZ,
    "N": UnitType.NEWTON,
    "Pa": UnitType.PASCAL,
    "J": UnitType.JOULE,
    "W": UnitType.WATT,
    "C": UnitType.COULOMB,
    "V": UnitType.VOLT,
    "F": UnitType.FARAD,
    "Ω": UnitType.OHM,
    "S": UnitType.SIEMENS,
    "Wb": UnitType.WEBER,
    "T": UnitType.TESLA,
    "H": UnitType.HENRY,
    "lm": UnitType.LUMEN,
    "lx": UnitType.LUX,
    "Bq": UnitType.BECQUEREL,
    "Gy": UnitType.GRAY,
    "Sv": UnitType.SIEVERT,
    "kat": UnitType.KATAL,
    "item": UnitType.ITEM,
    "L": UnitType.LITRE,
    "°C": UnitType.CELSIUS,
    "deg_C": UnitType.CELSIUS,
}
