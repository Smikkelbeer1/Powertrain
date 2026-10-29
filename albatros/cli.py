"""Command-line interface.  Run ``python -m albatros --help`` for all options.

Examples
  python -m albatros --mass 750                         one design, MTOW-driven
  python -m albatros --torque 600                       one design, torque-driven
  python -m albatros --sweep 600 1200 50 --csv out/sweep.csv --plot
  python -m albatros --sweep-torque 300 900 100 --csv out/torque_sweep.csv
  python -m albatros --write-config configs/my_inputs.json
  python -m albatros --config configs/my_inputs.json --mass 850 --json out/design.json
  python -m albatros --mass 750 --landing-recovery 600 10 5   overheat check for turn-back landing
  python -m albatros --mass 750 --cost-config configs/elct_cost_assumptions.json   other cost choices
"""
from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from .elct_cost_estimation import estimate_cost, load_cost_config
from .recovery import landing_recovery
from .reporting import (load_inputs, print_cost, print_design, print_recovery, sweep_row,
                        write_config, write_csv, write_json)
from .sizing import run_model, sweep_values


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m albatros", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    main_input = parser.add_mutually_exclusive_group()
    main_input.add_argument("--mass", type=float, help="MTOW-driven design at this MTOW [kg]")
    main_input.add_argument("--torque", type=float,
                            help="Torque-driven design: peak torque of each motor [Nm]")
    main_input.add_argument("--sweep", nargs=3, type=float, metavar=("START", "STOP", "STEP"),
                            help="Sweep MTOW [kg]")
    main_input.add_argument("--sweep-torque", nargs=3, type=float, metavar=("START", "STOP", "STEP"),
                            help="Sweep motor peak torque [Nm]")
    parser.add_argument("--config", type=Path, help="JSON file with input overrides")
    parser.add_argument("--write-config", type=Path, help="Write all inputs to JSON and exit")
    parser.add_argument("--csv", type=Path, help="Write mission time history (or sweep table)")
    parser.add_argument("--json", type=Path, help="Write full design (or sweep table) as JSON")
    parser.add_argument("--plot", action="store_true", help="Show plots")
    parser.add_argument("--save-plot", type=Path, help="Save the plot as PNG (works without --plot)")
    parser.add_argument("--inverter", choices=("efficiency", "device"), help="Inverter loss model")
    parser.add_argument("--parallel", type=int, help="Check a fixed Np instead of sizing it")
    parser.add_argument("--landing-recovery", nargs=3, type=float, metavar=("MAX", "STEP", "MARGIN"),
                        help="After sizing, find the shortest level cruise [s] (0..MAX in STEP) after "
                             "which descent, back-transition and landing stay MARGIN [C] below the "
                             "temperature limits (MAX 0 = turn back right after climb)")
    parser.add_argument("--cost-config", type=Path,
                        help="Cost assumptions / product selections JSON (ELCT cost estimation)")
    return parser


def design_cost(design: dict[str, Any], cost_config: dict[str, Any] | None) -> dict[str, Any]:
    """Cost report of a design. A costing problem (e.g. a part's voltage limit)
    is reported next to the design instead of discarding the physics result."""
    try:
        return estimate_cost(design, cost_config)
    except ValueError as exc:
        return {"error": str(exc)}


def run_sweep(x, variable: str, values: list[float],
              cost_config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Run one design per value; failed points keep their error message."""
    summary: list[dict[str, Any]] = []
    for value in values:
        trial = deepcopy(x)
        if variable == "mass_kg":
            trial.aircraft.mass_kg, trial.motor.peak_torque_Nm = value, 0.0
        else:
            trial.motor.peak_torque_Nm = value
        print(f"Calculating {variable} = {value:g} ...", flush=True)
        try:
            design = run_model(trial)
            row = sweep_row(variable, value, design, design_cost(design, cost_config))
        except ValueError as exc:
            row = {variable: value, "error": str(exc)}
        summary.append(row)
        print(json.dumps(row), flush=True)
    return summary


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        x = load_inputs(args.config)
        cost_config = load_cost_config(args.cost_config)
        if args.mass is not None:  # MTOW given on the command line wins
            x.aircraft.mass_kg, x.motor.peak_torque_Nm = args.mass, 0.0
        if args.torque is not None:
            x.motor.peak_torque_Nm = args.torque
        if args.inverter:
            x.inverter.mode = args.inverter
        if args.parallel is not None:
            x.battery.parallel_count = args.parallel
        if args.write_config:
            write_config(args.write_config, x)
            print("Wrote", args.write_config)
            return

        data: dict[str, Any] | list[dict[str, Any]]
        x_key, x_label = "mtow_kg", "MTOW (kg)"
        if args.landing_recovery and (args.sweep or args.sweep_torque):
            raise ValueError("--landing-recovery works on a single design, not a sweep")
        if args.sweep or args.sweep_torque:
            if args.sweep:
                data = run_sweep(x, "mass_kg", sweep_values(*args.sweep), cost_config)
            else:
                data = run_sweep(x, "peak_torque_Nm", sweep_values(*args.sweep_torque), cost_config)
                x_key, x_label = "peak_torque_Nm", "Motor peak torque (Nm)"
            if args.csv:
                write_csv(args.csv, data)
        else:
            data = run_model(x)
            data["cost_estimation"] = design_cost(data, cost_config)
            print_design(data)
            print_cost(data["cost_estimation"])
            if args.landing_recovery:
                data["landing_recovery"] = landing_recovery(x, data, *args.landing_recovery)
                print_recovery(data["landing_recovery"])
            if args.csv:
                write_csv(args.csv, data["mission_rows"])
        if args.json:
            write_json(args.json, data)
        if args.plot or args.save_plot:
            from .plotting import plot_results
            plot_results(data, args.save_plot, args.plot, x_key, x_label)
    except (ValueError, OSError, TypeError) as exc:
        parser.exit(2, f"Model input/output error: {exc}\n")
