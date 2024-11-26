from __future__ import annotations

from enum import Enum
from typing import Optional
from xml.dom import minidom

from astropy.units import Unit
from pydantic_xml import attr, element, BaseXmlModel


class UnitDefinition(
    BaseXmlModel,
    search_mode="unordered",
):
    """
    A class to represent a unit definition in XML format.

    Attributes:
        id (Optional[str]): The ID of the unit definition.
        name (Optional[str]): The name of the unit definition.
        base_units (list[BaseUnit]): A list of base units associated with the unit definition.
    """

    id: Optional[str] = attr(default=None, tag="id", json_schema_extra=dict())

    name: Optional[str] = attr(default=None, tag="name", json_schema_extra=dict())

    base_units: list[BaseUnit] = element(
        default_factory=list, tag="base_units", json_schema_extra=dict()
    )

    def add_to_base_units(
        self,
        kind: UnitType,
        exponent: int,
        multiplier: Optional[float] = None,
        scale: Optional[float] = None,
        **kwargs,
    ):
        """
        Add a base unit to the unit definition.

        Args:
            kind (UnitType): The type of the unit.
            exponent (int): The exponent of the unit.
            multiplier (Optional[float], optional): The multiplier of the unit. Defaults to None.
            scale (Optional[float], optional): The scale of the unit. Defaults to None.

        Returns:
            BaseUnit: The added base unit.
        """
        params = {
            "kind": kind,
            "exponent": exponent,
            "multiplier": multiplier,
            "scale": scale,
        }

        self.base_units.append(BaseUnit(**params))

        return self.base_units[-1]

    def xml(self, encoding: str = "unicode") -> str | bytes:
        """
        Converts the object to an XML string.

        Args:
            encoding (str, optional): The encoding to use. If set to "bytes", will return a bytes string.
                                      Defaults to "unicode".

        Returns:
            str | bytes: The XML representation of the object.
        """
        if encoding == "bytes":
            return self.to_xml()

        raw_xml = self.to_xml(encoding=None)
        parsed_xml = minidom.parseString(raw_xml)
        return parsed_xml.toprettyxml(indent="  ")


class BaseUnit(
    BaseXmlModel,
    search_mode="unordered",
):
    """
    A class to represent a base unit in XML format.

    Attributes:
        kind (UnitType): The type of the unit.
        exponent (int): The exponent of the unit.
        multiplier (Optional[float]): The multiplier of the unit.
        scale (Optional[float]): The scale of the unit.
    """

    kind: UnitType = attr(tag="kind", json_schema_extra=dict())

    exponent: int = attr(tag="exponent", json_schema_extra=dict())

    multiplier: Optional[float] = attr(
        default=None, tag="multiplier", json_schema_extra=dict()
    )

    scale: Optional[float] = attr(default=None, tag="scale", json_schema_extra=dict())

    def xml(self, encoding: str = "unicode") -> str | bytes:
        """
        Converts the object to an XML string.

        Args:
            encoding (str, optional): The encoding to use. If set to "bytes", will return a bytes string.
                                      Defaults to "unicode".

        Returns:
            str | bytes: The XML representation of the object.
        """
        if encoding == "bytes":
            return self.to_xml()

        raw_xml = self.to_xml(encoding=None)
        parsed_xml = minidom.parseString(raw_xml)
        return parsed_xml.toprettyxml(indent="  ")

    def to_astropy(self):
        """
        Converts the base unit to an astropy unit.

        Returns:
            Unit: The astropy unit representation of the base unit.
        """
        return Unit(self.name)


class UnitType(Enum):
    """
    An enumeration to represent different types of units.
    """

    AMPERE = "ampere"
    AVOGADRO = "avogadro"
    BECQUEREL = "becquerel"
    CANDELA = "candela"
    CELSIUS = "celsius"
    COULOMB = "coulomb"
    DIMENSIONLESS = "dimensionless"
    FARAD = "farad"
    GRAM = "gram"
    GRAY = "gray"
    HENRY = "henry"
    HERTZ = "hertz"
    ITEM = "item"
    JOULE = "joule"
    KATAL = "katal"
    KELVIN = "kelvin"
    KILOGRAM = "kilogram"
    LITRE = "litre"
    LUMEN = "lumen"
    LUX = "lux"
    METRE = "metre"
    MOLE = "mole"
    NEWTON = "newton"
    OHM = "ohm"
    PASCAL = "pascal"
    RADIAN = "radian"
    SECOND = "second"
    SIEMENS = "siemens"
    SIEVERT = "sievert"
    STERADIAN = "steradian"
    TESLA = "tesla"
    VOLT = "volt"
    WATT = "watt"
    WEBER = "weber"
