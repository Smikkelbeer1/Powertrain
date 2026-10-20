"""Albatros Model III - conceptual eVTOL powertrain sizing.

Typical use from Python:
    from albatros import Inputs, run_model
    x = Inputs()
    x.aircraft.mass_kg = 800
    result = run_model(x)
    print(result["parallel"], result["battery_dry_with_BMS_kg"])

See README.md for the model description and assumptions.
"""
from .inputs import Inputs
from .sizing import run_model

__all__ = ["Inputs", "run_model"]
