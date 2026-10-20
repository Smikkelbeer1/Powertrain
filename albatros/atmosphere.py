"""Standard atmosphere (troposphere only).

Reference: https://www.grc.nasa.gov/www/k-12/airplane/atmosmet.html
"""
from __future__ import annotations

import math

G0 = 9.80665  # gravity [m/s^2]
R_AIR = 287.05  # gas constant of air [J/kg/K]
LAPSE = 0.0065  # temperature lapse rate [K/m]


def atmosphere(msl_m: float, sea_level_C: float) -> tuple[float, float, float]:
    """Return (density kg/m^3, temperature degC, speed of sound m/s).

    Pressure follows the ISA troposphere. Temperature is ISA shifted by the
    chosen sea-level temperature (hot-day offset); density from the ideal gas law.
    """
    if not -500 <= msl_m <= 11000:
        raise ValueError("Atmosphere model requires -500 <= MSL altitude <= 11000 m")
    t_isa = 288.15 - LAPSE * msl_m
    pressure = 101325.0 * (t_isa / 288.15) ** (G0 / (R_AIR * LAPSE))
    temp_K = t_isa + sea_level_C - 15.0  # ISA + temperature offset
    rho = pressure / (R_AIR * temp_K)
    return rho, temp_K - 273.15, math.sqrt(1.4 * R_AIR * temp_K)
