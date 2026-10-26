"""Motor mass from peak torque, fitted on the HPDM motor family.

A power-law trendline is fitted to (peak torque, mass) of the HPDM motors:

    m = a * T_peak^b        (least squares on log(m) vs log(T_peak))

``mass_from_torque`` gives the motor mass the model uses for a required peak
torque; ``torque_from_mass`` is the inverse. Outside the data range
(4.1 .. 50 kg) the trendline is extrapolated and the model reports this.
Peak torques were read off the manufacturer's efficiency maps (approximate).
"""
from __future__ import annotations

import math

# name: (mass [kg], peak torque [Nm])
MOTORS: dict[str, tuple[float, float]] = {
    "HPDM-30": (4.1, 20.5),
    "HPDM-180-D": (13.7, 90.0),
    "HPDM-350": (50.0, 1420.0),
    "HPDM-500": (46.0, 590.0),
}


def _fit() -> tuple[float, float, float]:
    """Straight line through (log T, log m). Returns (a, b, R^2 in log space)."""
    xs = [math.log(t) for _, t in MOTORS.values()]
    ys = [math.log(m) for m, _ in MOTORS.values()]
    n = len(xs)
    x_mean, y_mean = sum(xs) / n, sum(ys) / n
    b = (sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
         / sum((x - x_mean) ** 2 for x in xs))
    log_a = y_mean - b * x_mean
    residual = sum((y - (log_a + b * x)) ** 2 for x, y in zip(xs, ys))
    total = sum((y - y_mean) ** 2 for y in ys)
    return math.exp(log_a), b, 1 - residual / total


A_COEF, B_EXP, R2_LOG = _fit()
MASS_RANGE_KG = (min(m for m, _ in MOTORS.values()), max(m for m, _ in MOTORS.values()))


def mass_from_torque(torque_Nm: float) -> float:
    """Motor mass [kg] for a given peak torque [Nm] (trendline)."""
    return A_COEF * torque_Nm ** B_EXP


def torque_from_mass(mass_kg: float) -> float:
    """Peak torque [Nm] of a motor with the given mass [kg] (inverse trendline)."""
    return (mass_kg / A_COEF) ** (1.0 / B_EXP)


def describe() -> str:
    """One-line summary of the fitted trendline (printed in reports)."""
    return f"m = {A_COEF:.4f} * T_peak^{B_EXP:.4f}  (R^2 log = {R2_LOG:.3f})"
