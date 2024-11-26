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
import json
import math
from json import JSONDecodeError

import astropy.units as u
from astropy.units import (
    Unit,
    PrefixUnit,
    IrreducibleUnit,
    UnitBase,
    CompositeUnit,
)

from .mappings import UNIT_MAPPING
from .unit_definition import UnitType, UnitDefinition


def convert_unit(unit: str):
    if isinstance(unit, dict):
        return UnitDefinition(**unit)

    try:
        return UnitDefinition(**json.loads(unit))
    except JSONDecodeError:
        return _convert_unit_string(unit)


def _convert_unit_string(unit_string: str):
    if unit_string == "absorbance":
        unit_def = UnitDefinition(id="absorbance", name="absorbance")
        _dimensionless_unit(unit_def)

        return unit_def

    unit = Unit(unit_string)
    unit_def = UnitDefinition(id=unit.to_string(), name=unit.to_string())

    if isinstance(unit, CompositeUnit):
        _process_composite_unit(unit, unit_def)
    elif len(unit.decompose().bases) > 1:
        _process_composite_unit(unit.decompose(), unit_def)
    else:
        _process_base_unit(unit_def, unit, 1)

    return unit_def


def _process_composite_unit(unit, unit_def):
    bases = unit.bases

    if unit.scale != 1.0:
        _dimensionless_unit(
            unit_def=unit_def,
            multiplier=unit.scale,
        )

    if not bases:
        _dimensionless_unit(unit_def)
    for base, exponent in zip(bases, unit.powers):
        if len(base.decompose().bases) > 1:
            _process_composite_unit(base.decompose(), unit_def)
        else:
            _process_base_unit(unit_def, base, exponent)


def _dimensionless_unit(
    unit_def: UnitDefinition,
    scale: float = 1.0,
    multiplier: float = 1.0,
    exponent: int = 1,
):
    unit_def.add_to_base_units(
        kind=UnitType.DIMENSIONLESS,
        exponent=exponent,
        scale=scale,
        multiplier=multiplier,
    )


def _process_base_unit(
    unit_def: UnitDefinition,
    base: Unit | PrefixUnit | IrreducibleUnit | UnitBase,
    exponent: int,
):
    if base.is_equivalent(u.liter):
        scale = base.to(u.liter)
        unit_def.add_to_base_units(
            kind=UnitType.LITRE,
            exponent=exponent,
            scale=int(scale),
            multiplier=1.0,
        )
    elif base.is_equivalent(u.gram):
        scale = base.to(u.gram)
        unit_def.add_to_base_units(
            kind=UnitType.GRAM,
            exponent=exponent,
            scale=scale,
            multiplier=1.0,
        )
    elif isinstance(base, PrefixUnit):
        base = base.decompose()
        unit_def.add_to_base_units(
            kind=UNIT_MAPPING[base.bases[0].to_string()],
            exponent=exponent,
            scale=int(math.log10(base.scale)),
            multiplier=1.0,
        )
    elif isinstance(base, Unit):
        if base.is_equivalent(u.second):
            base = base.decompose()
            unit_def.add_to_base_units(
                kind=UNIT_MAPPING[base.bases[0].to_string()],
                exponent=exponent,
                scale=1,
                multiplier=base.scale,
            )
        else:
            unit_def.add_to_base_units(
                kind=UNIT_MAPPING[base.bases[0].to_string()],
                exponent=exponent,
                scale=1,
                multiplier=1.0,
            )
    elif isinstance(base, IrreducibleUnit):
        unit_def.add_to_base_units(
            kind=UNIT_MAPPING[base.bases[0].to_string()],
            exponent=exponent,
            scale=int(math.log10(base.scale)),
            multiplier=1.0,
        )
    else:
        raise ValueError(f"Unknown base type: {type(base)}")
