"""Reading inputs (JSON) and writing results (terminal, CSV, JSON)."""
from __future__ import annotations

import csv
import json
from dataclasses import asdict, fields
from pathlib import Path
from typing import Any

from .inputs import Inputs


def load_inputs(path: Path | None) -> Inputs:
    """Defaults from inputs.py, overridden by whatever the JSON file contains.

    The JSON file may contain only the values you want to change, e.g.
        {"aircraft": {"mass_kg": 850}, "propeller": {"model": "coefficients"}}
    Unknown sections/keys raise an error (catches typos).
    """
    x = Inputs()
    if path is None:
        return x
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Configuration must be a JSON object")
    for section, overrides in data.items():
        if section.startswith("_"):  # "_comment" keys are allowed for notes
            continue
        if section not in {f.name for f in fields(x)} or not isinstance(overrides, dict):
            raise ValueError("Unknown config section or non-object: " + section)
        obj = getattr(x, section)
        valid = {f.name for f in fields(obj)}
        for key, value in overrides.items():
            if key.startswith("_"):
                continue
            if key not in valid:
                raise ValueError(f"Unknown input {section}.{key}")
            if isinstance(getattr(obj, key), tuple):  # JSON lists -> tuples
                value = tuple(tuple(v) if isinstance(v, list) else v for v in value)
            setattr(obj, key, value)
    return x


def write_config(path: Path, x: Inputs) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(x), indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def sweep_row(variable: str, value: float, r: dict[str, Any]) -> dict[str, Any]:
    """Compact one-line summary of a design, used for sweeps."""
    return {variable: value, "mtow_kg": r["mtow_kg"], "series": r["series"],
            "parallel": r["parallel"], "cell_count": r["cell_count"],
            "battery_cells_kg": r["battery_cells_kg"], "battery_dry_kg": r["battery_dry_with_BMS_kg"],
            "motors_kg": r["motors_total_kg"],
            "max_rated_torque_Nm": max(d["rated_torque_Nm"] for d in r["drive_requirements"]),
            "cooling_kg": r["cooling_total_kg"], "remaining_kg": r["remaining_MTOW_kg"],
            "battery_volume_L": r["volumes_L"]["battery_packs"],
            "radiator_volume_L": r["volumes_L"]["radiator"], "total_volume_L": r["total_volume_L"],
            "mission_kWh": r["nominal_metrics"]["terminal_energy_kWh"],
            "end_soc": r["nominal_metrics"]["end_min_group_soc"],
            "worst_motor_C": r["all_case_metrics"]["peak_motor_C"],
            "worst_inverter_C": r["all_case_metrics"]["peak_inverter_C"],
            "worst_battery_C": r["all_case_metrics"]["peak_battery_C"],
            "issues": "; ".join(r["issues"])}


def print_design(result: dict[str, Any]) -> None:
    """Human-readable summary of one design."""
    r, m = result, result["nominal_metrics"]
    inp = r["inputs"]
    driver = ("imposed MTOW" if r["design_driver"] == "MTOW"
              else f"MTOW found for {inp['motor']['peak_torque_Nm']:.1f} Nm motors")
    print(f"\nAlbatros Model III | {driver}: {r['mtow_kg']:.1f} kg")
    print(f"Propeller model: {inp['propeller']['model']} | drag model: {inp['aerodynamics']['drag_model']}"
          f" | motor mass: {inp['motor']['mass_model']}")
    print("\n-- Battery --")
    print(f"{r['series']}S {r['parallel']}P = {r['cell_count']} cells | charge ceiling "
          f"{r['full_charge_V']:.1f} V | nominal {r['nominal_V']:.1f} V")
    print(f"Nominal energy {r['nominal_energy_kWh']:.1f} kWh | mission terminal energy "
          f"{m['terminal_energy_kWh']:.1f} kWh")
    print(f"Nominal end weakest SOC {100 * m['end_min_group_soc']:.1f}% | minimum bus "
          f"{m['min_bus_V']:.1f} V | peak cell {m['peak_cell_A']:.1f} A")
    print("Sizing mode:", r["sizing_mode"], "| peak nominal current phase:", r["peak_current_nominal_phase"])
    print("Why not one parallel string fewer:", ", ".join(r["previous_parallel_failure"]))
    balance = r["balancing"]
    hours = balance["estimated_ground_hours"]
    print(f"Passive balance: {balance['series_group_channels']} channels, "
          f"{balance['on_current_A'] * 1000:.0f} mA ON, estimated ground time "
          f"{hours if hours is None else round(hours, 2)} h")

    print("\n-- Mass budget --")
    print(f"Cells {r['battery_cells_kg']:.1f} kg | battery incl packaging/BMS {r['battery_dry_with_BMS_kg']:.1f} kg")
    inverters = ("integrated in motors" if inp["inverter"]["integrated_in_motor"]
                 else f"{r['inverters_total_kg']:.1f} kg")
    print(f"Motors {r['motors_total_kg']:.1f} kg | inverters {inverters} | "
          f"cooling {r['cooling_total_kg']:.1f} kg | avionics {r['avionics_kg']:.1f} kg")
    print(f"Total powertrain/systems {r['accounted_subsystems_kg']:.1f} kg | remaining MTOW for "
          f"airframe, rotors, payload etc: {r['remaining_MTOW_kg']:.1f} kg")

    print("\n-- Volume budget (L) --")
    v = r["volumes_L"]
    print(f"Battery packs {v['battery_packs']:.1f} (bare cells {r['battery_bare_volume_L']:.1f}) | "
          f"radiators {v['radiator']:.1f} | fans {v['fan']:.1f} | pumps {v['pump']:.1f}")
    print(f"Hoses {v['hoses']:.1f} | reservoirs {v['reservoir']:.1f} | motors {v['motors']:.1f} | "
          f"inverters {v['inverters']:.1f} | avionics {v['avionics']:.1f}")
    print(f"Total {r['total_volume_L']:.1f} L")
    print("Per pod   battery section L  radiator core L  radiators fit pod")
    for p in r["radiator_packaging"]:
        print(f"{p['pod']:9} {p['battery_section_envelope_L']:17.1f} {p['radiator_core_L']:16.1f}  "
              f"{'yes' if p['fits_core_allowance'] else 'NO'}")

    print("\n-- Motors (HPDM fit: " + r["motor_family_fit"] + ") --")
    print("Rotor        rated kW  rated Nm  mass kg   max Nm  phase A  max rpm  elec Hz")
    for d in r["drive_requirements"]:
        print(f"{d['rotor']:11} {d['installed_peak_requirement_kW']:9.1f} {d['rated_torque_Nm']:9.1f} "
              f"{d['motor_mass_kg']:8.1f} {d['max_torque_Nm']:8.1f} {d['max_phase_rms_A']:8.1f} "
              f"{d['max_rpm']:8.0f} {d['max_electrical_Hz']:8.0f}")

    print("\n-- Cooling --")
    print(f"Nominal peak temperatures: cells {m['peak_battery_C']:.1f}, motor {m['peak_motor_C']:.1f}, "
          f"inverter {m['peak_inverter_C']:.1f} C")
    print("Loop                    L/min   head kPa   pump W fan rated W  core L   UA W/K")
    for l in r["cooling_loops"]:
        print(f"{l['name']:23} {l['flow_L_min']:6.2f} {l['pump_head_Pa'] / 1000:10.1f} {l['pump_W']:8.1f} "
              f"{l['fan_rating_W']:8.1f} {l['core_m3'] * 1000:9.2f} {l['UA_W_K']:8.1f}")

    print("\n-- Checks --")
    print(f"Worst contingency end weakest SOC: {100 * r['worst_contingency_end_soc']:.1f}%")
    print(f"Emergency cases checked independently: {len(r['emergencies'])} "
          f"(duration {inp['aircraft']['emergency_s']:.0f} s each)")
    print("MODEL LIMIT EXCEEDANCES:", "; ".join(r["issues"]) or "none under stated assumptions")
    for note in r["warnings"]:
        print("Assumption:", note)


def print_recovery(r: dict[str, Any]) -> None:
    """Human-readable summary of the thermal landing-recovery search."""
    limits = r["limits_C"]
    print(f"\n-- Landing recovery (margin {r['margin_C']:g} C below limits: cells "
          f"{limits['battery']:g}, motor {limits['motor']:g}, inverter {limits['inverter']:g} C) --")
    print("Outbound:", " -> ".join(r["prefix_phases"]))
    print("Landing: ", " -> ".join(r["landing_phases"]))
    if r["trials"]:
        print("cruise s  cells C  motor C  inv C  end SOC %  result")
    for t in r["trials"]:
        print(f"{t['cruise_s']:8.1f} {t['peak_battery_C']:8.1f} {t['peak_motor_C']:8.1f} "
              f"{t['peak_inverter_C']:6.1f} {100 * t['end_min_group_soc']:10.1f}  "
              f"{'PASS' if t['passed'] else 'fail: ' + '; '.join(t['reasons'])}")
    if r["feasible"]:
        when = ("immediately after climb" if r["earliest_cruise_s"] == 0
                else f"after {r['earliest_cruise_s']:g} s level cruise (sampled every {r['step_s']:g} s)")
        print("RESULT: landing is thermally possible", when)
    else:
        print("RESULT: landing NOT possible -", r["stop_reason"])
