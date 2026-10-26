"""Passive cell balancing estimate (ground top-balancing workload).

One bleed-resistor channel per SERIES GROUP (each group = Np parallel cells).
Charge to remove from a group = Np * capacity * SOH * (its SOC excess).
Boards can only bleed a few channels at once and are limited by their own
temperature, which reduces the effective duty cycle.

This is NOT a charger simulation. The flight model simply starts with the
residual imbalance ``Battery.residual_soc_spread``.
Reference: https://www.ti.com/lit/an/sluaa81a/sluaa81a.pdf
"""
from __future__ import annotations

from typing import Any

from .electrical import board_count, ocv, section_counts
from .inputs import Inputs


def balancing_report(x: Inputs, ns: int, np: int) -> dict[str, Any]:
    z, b, cell = x.balancing, x.battery, x.cell
    voltage = ocv(b.initial_soc, cell)
    on_A = voltage / (z.resistor_ohm + z.switch_ohm)  # bleed current while ON
    resistor_W = on_A ** 2 * z.resistor_ohm
    fet_W = on_A ** 2 * z.switch_ohm
    heat_per_channel = resistor_W + fet_W
    # How much heat a board may dissipate before it hits its temperature limit
    thermal_budget_W = max(0.0, (z.board_limit_C - x.cooling.sea_level_ambient_C) # T_board - T_ambient / W_board to air - W board
                           / z.board_to_ambient_K_W - z.board_base_W)
    duty = min(z.duty, thermal_budget_W / (z.simultaneous_per_board * heat_per_channel))
    target = b.residual_soc_spread
    spread = z.initial_soc_spread
    excess = max(0.0, spread - target)
    worst_Ah = np * cell.capacity_Ah * b.soh * excess
    max_boards_time_h = 0.0
    total_removed_Ah = 0.0
    max_board_heat_W = 0.0
    for count in section_counts(ns):
        for first in range(0, count, z.channels_per_board):
            n = min(z.channels_per_board, count - first)  # channels on this board
            # Group SOCs evenly spread over the initial spread; every group above
            # the target must be bled down to it.
            charges = [np * cell.capacity_Ah * b.soh
                       * max(0.0, spread * i / max(1, n - 1) - target) for i in range(n)]
            total_removed_Ah += sum(charges)
            if duty > 0:
                # Board is done when its worst channel is done, or when the total
                # work shared over the simultaneous channels is done.
                board_time = (max(max(charges, default=0.0),
                                  sum(charges) / z.simultaneous_per_board) / (on_A * duty))
                max_boards_time_h = max(max_boards_time_h, board_time)
            max_board_heat_W = max(max_board_heat_W,
                                   min(n, z.simultaneous_per_board) * heat_per_channel * duty
                                   + z.board_base_W)
    issues: list[str] = []
    if resistor_W > z.resistor_rating_W * z.resistor_usable_fraction:
        issues.append("Bleed resistor exceeds derated ON-state power rating")
    if b.initial_soc - spread < z.minimum_balancing_soc:
        issues.append("Some groups below chosen top-balancing SOC threshold; charging model needed")
    if duty <= 0 and excess > 0:
        issues.append("No board thermal budget for balancing")
    return dict(
        enabled=z.enabled, series_group_channels=ns, monitor_boards=board_count(ns, z),
        on_current_A=on_A, effective_duty=duty, average_channel_A=on_A * duty,
        resistor_on_W=resistor_W, switch_on_W=fet_W,
        worst_group_charge_to_remove_Ah=worst_Ah,
        estimated_ground_hours=max_boards_time_h if z.enabled and duty > 0 else None,
        ground_energy_dissipated_Wh=voltage * total_removed_Ah if z.enabled else 0.0,
        maximum_board_heat_W=max_board_heat_W,
        estimated_board_C=x.cooling.sea_level_ambient_C + z.board_to_ambient_K_W * max_board_heat_W,
        hardware_mass_kg=(board_count(ns, z) * z.board_mass_kg + ns * z.channel_mass_kg
                          + z.master_and_harness_kg),
        flight_balancing_W=0.0, issues=issues,
        note="Ground-only constant-voltage workload estimate; residual flight imbalance "
             "is an input, not a simulated charging outcome.")
