"""Cost estimation checks.  Run with:  python -m pytest"""
from __future__ import annotations

import copy
import json
import math
from functools import lru_cache

import pytest

from albatros.cli import run_sweep
from albatros.elct_cost_estimation import CATALOG, estimate_cost, optimizer_objective
from albatros.inputs import Inputs
from albatros.sizing import run_model


@lru_cache(maxsize=1)
def _design() -> str:
    return json.dumps(run_model(Inputs()))  # default 750 kg design, run once


def design() -> dict:
    return json.loads(_design())


def test_total_reconciles():
    r = estimate_cost(design())
    for k in ("low", "base", "high"):
        assert math.isclose(sum(x["subtotal_eur"][k] for x in r["rows"]), r["subtotal_eur"][k], abs_tol=0.05)
        assert math.isclose(r["subtotal_eur"][k] * 1.2, r["total_eur"][k], abs_tol=0.05)


def test_parallel_scaling_and_board_count():
    d = design()
    double = copy.deepcopy(d)
    double["parallel"] *= 2
    double["cell_count"] *= 2
    a, b = estimate_cost(d), estimate_cost(double)
    assert b["quantities"]["cells"] == a["quantities"]["cells"] * 2
    sections = [d["series"] // 4 + (i < d["series"] % 4) for i in range(4)]
    assert a["quantities"]["bms_boards"] == sum(math.ceil(n / 12) for n in sections)
    assert b["quantities"]["bms_boards"] == a["quantities"]["bms_boards"]  # series groups, not cells


def test_inverters_follow_model_and_are_not_counted_twice():
    d = design()
    assert d["inputs"]["inverter"]["integrated_in_motor"]  # model default
    integrated = estimate_cost(d)
    separate = estimate_cost(d, {"integrated_inverters": False})
    assert integrated["quantities"]["inverters"] == 0
    assert separate["quantities"]["inverters"] == len(d["drive_requirements"])
    inverter = next(x for x in separate["rows"] if x["category"] == "inverter")
    assert math.isclose(separate["subtotal_eur"]["base"] - integrated["subtotal_eur"]["base"],
                        inverter["subtotal_eur"]["base"], abs_tol=0.05)
    d["inputs"]["inverter"]["integrated_in_motor"] = False
    assert estimate_cost(d)["quantities"]["inverters"] == len(d["drive_requirements"])


def test_family_mismatch_rejected():
    with pytest.raises(ValueError):
        estimate_cost(design(), {"selection": {"bms_monitor": "bms_monitor_3"}})


def test_cell_change_requires_model_update():
    with pytest.raises(ValueError):
        estimate_cost(design(), {"selection": {"cells": "cells_2"}})


def test_voltage_limit():
    d = design()
    d["full_charge_V"] = 900
    with pytest.raises(ValueError):
        estimate_cost(d, {"integrated_inverters": False})


@pytest.mark.parametrize("cfg", [
    {"hv_cable_m": -1}, {"hv_cable_m": float("nan")}, {"selection": {"bad": "bad"}},
    {"price_overrides_eur": {"cells": {"low": 2, "base": 1, "high": 3}}},
    {"quantity_overrides": {"cells": 1}}, {"packs": 2}, {"not_a_setting": 1}])
def test_missing_or_invalid_data_rejected(cfg):
    with pytest.raises(ValueError):
        estimate_cost(design(), cfg)


def test_objective_cannot_hide_infeasible_design():
    d = design()
    d["issues"] = ["some exceedance"]
    assert math.isinf(optimizer_objective(d, allow_provisional=True))
    d["issues"] = []
    with pytest.raises(ValueError):
        optimizer_objective(d)
    assert optimizer_objective(d, allow_provisional=True) > 0


def test_strict_refuses_unverified_catalogue():
    with pytest.raises(ValueError):
        estimate_cost(design(), {"strict": True})


def test_overrides_and_optional_equipment():
    d = design()
    r = estimate_cost(d, {"price_overrides_eur": {"cells": {"low": 2, "base": 3, "high": 4}},
                          "include_ground": False, "include_nre": False})
    cells = next(x for x in r["rows"] if x["category"] == "cells")
    assert cells["subtotal_eur"]["base"] == d["cell_count"] * 3
    assert cells["price_status"] == "user_estimate"
    assert r["scope_totals_eur"]["ground"]["base"] == 0
    assert r["scope_totals_eur"]["nre"]["base"] == 0


def test_catalogue_completeness():
    c = json.loads(CATALOG.read_text(encoding="utf-8"))
    ids = []
    for category in c["categories"]:
        assert len(category["products"]) >= 5
        for p in category["products"]:
            assert p["technical_source"].startswith("https://")
            ids.append(p["id"])
    assert len(ids) == len(set(ids))


def test_sweep_rows_carry_cost():
    rows = run_sweep(Inputs(), "mass_kg", [750.0])
    assert rows[0]["cost_base_eur"] > 0 and rows[0]["cost_error"] == ""
