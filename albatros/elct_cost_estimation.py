"""Electrical/thermal powertrain cost estimate (ELCT cost estimation).

Prices one run_model() result with the product catalogue in
elct-cost-estimation.json (next to this file). Motors are excluded. Values are
EUR excluding VAT, freight and import duty, as low / base / high scenarios.

    from albatros import Inputs, run_model
    from albatros.elct_cost_estimation import estimate_cost, optimizer_objective
    design = run_model(Inputs())
    cost = estimate_cost(design)                 # full report
    cost["total_eur"]                            # {"low": ..., "base": ..., "high": ...}
    optimizer_objective(design, allow_provisional=True)   # base EUR, inf if infeasible

Only 8 of the 130 catalogue prices are public listings; the rest are author
estimates. The result is a PROVISIONAL budget for comparing designs, never a
procurement-ready BOM. See docs/cost/component-selection-guide.md.

Standalone (cost an exported design without rerunning the physics):
    python -m albatros.elct_cost_estimation out/design.json --config configs/elct_cost_assumptions.json --out out/cost.json
"""
from __future__ import annotations

import argparse
import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any

from .electrical import section_counts

CATALOG = Path(__file__).resolve().parent / "elct-cost-estimation.json"
SCENARIOS = ("low", "base", "high")

# Every setting a cost config may change. None = take it from the design.
DEFAULTS: dict[str, Any] = {
    "selection": {}, "price_overrides_eur": {}, "quantity_overrides": {},
    "integrated_inverters": None,  # None -> inputs.inverter.integrated_in_motor
    "inverter_coldplates_included": True,
    "electrical_islands": 1, "packs": 1,
    "battery_sections": None,  # None -> the model's battery sections (one per pod)
    "main_contactors": 6, "precharge_relays": 1, "resistor_networks": 2,
    "branch_fuses": 4, "dc_dc_units": 2,
    "hv_connector_pairs": 16, "hv_cable_m": 30,
    "current_sensors": 1, "voltage_sensors": 2,
    "qd_pairs_per_loop": 2, "temperature_probes_per_loop": 2,
    "pressure_sensors_per_loop": 1, "flow_meters_per_loop": 0,
    "rotors": 4, "shaft_assemblies": 0, "gearboxes": 0, "tilt_actuators": 0,
    "flight_computers": 0, "external_filters": 0, "external_dc_links": 0,
    "bms_interfaces": 1, "heaters": 0,
    "fans_per_loop": 1, "labour_hours": 160, "include_ground": True,
    "include_nre": True, "contingency_fraction": 0.20,
    "strict": False,
    "custom_radiator_reference_UA_W_K": 1000,
    "custom_radiator_cost_exponent": 0.7,
}
BOOLEANS = ("inverter_coldplates_included", "include_ground", "include_nre", "strict")
COUNTS = ("main_contactors", "precharge_relays", "resistor_networks", "branch_fuses",
          "hv_connector_pairs", "current_sensors", "voltage_sensors", "rotors", "shaft_assemblies",
          "gearboxes", "tilt_actuators", "flight_computers", "external_filters",
          "external_dc_links", "bms_interfaces", "heaters")
# Counts that follow from the engineering design: change the design, not the cost config.
FIXED_QUANTITIES = {"cells", "series", "packs", "bms_boards", "loops", "battery_sections"}
ALLOWANCE_SCOPE = {"ground_charger": "ground", "nre": "nre", "assembly": "labour"}


def _nonnegative(value: Any, label: str, zero: bool = True) -> float:
    if (isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value)
            or value < 0 or (not zero and value == 0)):
        raise ValueError(f"{label} must be a finite {'nonnegative' if zero else 'positive'} number")
    return value


def _integer(value: Any, label: str, zero: bool = False) -> int:
    _nonnegative(value, label, zero)
    if int(value) != value:
        raise ValueError(f"{label} must be an integer")
    return int(value)


@lru_cache(maxsize=4)
def _load_catalog(path: str) -> dict[str, Any]:
    """Catalogue is read once per path (the optimiser calls estimate_cost many times)."""
    catalog = json.loads(Path(path).read_text(encoding="utf-8"))
    if catalog["schema_version"] != 1:
        raise ValueError("Unsupported cost catalogue version")
    return catalog


def load_cost_config(path: Path | None) -> dict[str, Any] | None:
    return json.loads(path.read_text(encoding="utf-8")) if path else None


def _settings(design: dict[str, Any], config: dict[str, Any] | None) -> dict[str, Any]:
    cfg = dict(DEFAULTS)
    if config:
        unknown = set(config) - set(cfg)
        if unknown:
            raise ValueError("Unknown cost settings: " + ", ".join(sorted(unknown)))
        cfg.update(config)
    if cfg["integrated_inverters"] is None:
        cfg["integrated_inverters"] = bool(design["inputs"]["inverter"]["integrated_in_motor"])
    if cfg["battery_sections"] is None:
        cfg["battery_sections"] = len(section_counts(design["series"]))
    for key in BOOLEANS + ("integrated_inverters",):
        if not isinstance(cfg[key], bool):
            raise ValueError(f"{key} must be boolean")
    for key, value in cfg.items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            _nonnegative(value, key)
    for key in ("electrical_islands", "packs", "battery_sections", "dc_dc_units"):
        _integer(cfg[key], key)
    for key in COUNTS:
        _integer(cfg[key], key, zero=True)
    if cfg["contingency_fraction"] > 1:
        raise ValueError("contingency_fraction must be between 0 and 1")
    # Model III is one series string split into sections. Independent wing packs
    # need a pack-aware electrical model and their own interconnection BOM.
    if cfg["packs"] != 1:
        raise ValueError("Model III describes one series pack; cost independent packs separately")
    return cfg


def _select_products(catalog: dict[str, Any], cfg: dict[str, Any]) -> dict[str, dict[str, Any]]:
    categories = {c["id"]: c for c in catalog["categories"]}
    selection = {**catalog["default_selection"], **cfg["selection"]}
    if set(selection) != set(categories):
        raise ValueError("Selection contains unknown or missing categories")
    selected = {}
    for key, category in categories.items():
        found = [p for p in category["products"] if p["id"] == selection[key]]
        if len(found) != 1:
            raise ValueError(f"Unknown product {selection[key]} for {key}")
        selected[key] = found[0]
    if selected["bms_master"]["bms_family"] != selected["bms_monitor"]["bms_family"]:
        raise ValueError("BMS controller and monitor board families must match")
    if selected["precharge_relay"].get("role") == "discharge_only" and cfg["precharge_relays"]:
        raise ValueError("Normally-closed discharge relay cannot be selected as precharge relay")
    return selected


def _quantities(design: dict[str, Any], cfg: dict[str, Any],
                selected: dict[str, dict[str, Any]]) -> dict[str, float]:
    """Bill-of-material quantities from the sized design plus the cost config."""
    ns = _integer(design["series"], "design.series")
    np = _integer(design["parallel"], "design.parallel")
    if design["cell_count"] != ns * np:
        raise ValueError("cell_count differs from series * parallel")
    loops = design["cooling_loops"]
    if not loops:
        raise ValueError("cooling_loops must not be empty")
    cell, cooling = design["inputs"]["cell"], design["inputs"]["cooling"]
    sections = cfg["battery_sections"]
    section_series = [ns // sections + (i < ns % sections) for i in range(sections)]
    if min(section_series) < 1:
        raise ValueError("More battery sections than series groups")
    # Monitor boards measure series groups, rounded up in every section separately.
    boards = sum(math.ceil(n / selected["bms_monitor"]["channels"]) for n in section_series)
    battery_loops = [l for l in loops if l["is_battery"]]
    if not battery_loops:
        raise ValueError("Battery plate geometry unavailable; supply a cost adapter for a shared-loop model")
    # Wetted plate layout area: proxy until plate drawings allow a real quote.
    plate_width = cell["height_m"] if cell["form"] == "cylindrical" else cell["width_m"]
    plate_area = sum(l["acquisition"]["branches"] * l["acquisition"]["channel_length_m"] * plate_width
                     for l in battery_loops)
    tim_each = (cell["contact_fraction"] * math.pi * cell["diameter_m"] * cell["height_m"]
                if cell["form"] == "cylindrical" else cell["width_m"] * cell["height_m"])
    rho = _nonnegative(cooling["coolant_rho_kg_m3"], "coolant density", zero=False)
    drives = len(design["drive_requirements"])
    q: dict[str, float] = dict(
        cells=ns * np, series=ns, packs=cfg["packs"], battery_sections=sections,
        bms_boards=boards,
        inverters=0 if cfg["integrated_inverters"] else drives,
        external_inverter_plates=(0 if cfg["integrated_inverters"] or cfg["inverter_coldplates_included"]
                                  else drives),
        battery_plate_area=plate_area, tim_area=ns * np * tim_each,
        loops=len(loops), fans=len(loops) * cfg["fans_per_loop"],
        hose_m=sum(cooling["battery_line_length_m"] if l["is_battery"] else cooling["prop_line_length_m"]
                   for l in loops),
        qd_pairs=len(loops) * cfg["qd_pairs_per_loop"],
        temperature_probes=len(loops) * cfg["temperature_probes_per_loop"],
        pressure_sensors=len(loops) * cfg["pressure_sensors_per_loop"],
        flow_meters=len(loops) * cfg["flow_meters_per_loop"],
        coolant_L=sum(l["coolant_kg"] for l in loops) * 1000 / rho,
        aircraft=1, ground=int(cfg["include_ground"]), project=int(cfg["include_nre"]),
        electrical_islands=cfg["electrical_islands"], dc_dc_units=cfg["dc_dc_units"],
        hv_cable_m=cfg["hv_cable_m"], labour_hours=cfg["labour_hours"],
        **{k: cfg[k] for k in COUNTS})
    overrides = cfg["quantity_overrides"]
    if set(overrides) - set(q):
        raise ValueError("Unknown quantity override: " + ", ".join(sorted(set(overrides) - set(q))))
    if set(overrides) & FIXED_QUANTITIES:
        raise ValueError("Cannot override topology or cell/board counts; change the engineering design")
    q.update(overrides)
    for key, value in q.items():
        _nonnegative(value, key)
    return q


def estimate_cost(design: dict[str, Any], config: dict[str, Any] | None = None,
                  catalog_path: Path | str | None = None) -> dict[str, Any]:
    """Cost one run_model() result (not mutated). Missing data raises, never costs zero.

    config: optional dict with any keys of DEFAULTS (see configs/elct_cost_assumptions.json).
    Price overrides are treated as user estimates, not verified quotations.
    """
    cfg = _settings(design, config)
    catalog = _load_catalog(str(catalog_path or CATALOG))
    selected = _select_products(catalog, cfg)
    q = _quantities(design, cfg, selected)
    cell_name = design["inputs"]["cell"].get("name", "").lower()
    if selected["cells"]["cell_model"].lower() not in cell_name:
        raise ValueError("Selected cell does not match inputs.cell.name; rerun the model with matching cell data")
    loops = design["cooling_loops"]
    price_overrides = cfg["price_overrides_eur"]
    known = {c["id"] for c in catalog["categories"]} | {a["id"] for a in catalog["allowances"]}
    if set(price_overrides) - known:
        raise ValueError("Unknown price override category: "
                         + ", ".join(sorted(set(price_overrides) - known)))

    rows: list[dict[str, Any]] = []
    unresolved: list[str] = []

    def add(key: str, title: str, product: str, unit: str, qty: float, prices: dict[str, float],
            status: str, source: str | None = None, scope: str = "airborne", scale: float = 1.0) -> None:
        if key in price_overrides:
            prices, status = price_overrides[key], "user_estimate"
        if set(prices) != set(SCENARIOS):
            raise ValueError(f"{key}: prices need low/base/high")
        for k, v in prices.items():
            _nonnegative(v, f"{key}.{k}")
        if not prices["low"] <= prices["base"] <= prices["high"]:
            raise ValueError(f"{key}: price bounds out of order")
        if qty and prices["base"] == 0:
            raise ValueError(f"{key}: positive quantity cannot have zero price; use zero quantity for included parts")
        rows.append(dict(category=key, title=title, product=product, unit=unit, quantity=qty,
                         unit_price_eur=prices, scaling_factor=scale,
                         subtotal_eur={k: round(v * qty * scale, 2) for k, v in prices.items()},
                         price_status=status, price_source=source, scope=scope))

    for category in catalog["categories"]:
        key, p = category["id"], selected[category["id"]]
        qty = q[category["quantity_basis"]]
        scale = 1.0
        if key == "radiator" and p.get("custom"):
            # Assumed power law in UA (not a supplier pricing law), averaged over the loops.
            ref = _nonnegative(cfg["custom_radiator_reference_UA_W_K"], "reference UA", zero=False)
            scale = sum(max(l["UA_W_K"] / ref, 0.1) ** cfg["custom_radiator_cost_exponent"]
                        for l in loops) / len(loops)
        if qty:
            vmax = p.get("max_voltage_V")
            if vmax is not None and design["full_charge_V"] > vmax:
                raise ValueError(f"{p['name']}: {design['full_charge_V']:.0f} V exceeds its {vmax} V operating limit")
            unresolved.append(f"{key}: sizing and flight qualification unresolved")
        add(key, category["title"], p["name"], category["unit"], qty, p["price_eur"],
            p["price_status"], p["price_source"], scale=scale)
    for a in catalog["allowances"]:
        qty = q[a["quantity_basis"]]
        add(a["id"], a["title"], "UNRESOLVED CUSTOM/ASSEMBLY ALLOWANCE", a["quantity_basis"], qty,
            a["unit_price_eur"], a["price_status"], scope=ALLOWANCE_SCOPE.get(a["id"], "airborne"))
        if qty:
            unresolved.append(a["id"] + ": no verified five-product comparison or supplier quote")
    unresolved.extend("engineering_model: " + s for s in design.get("issues", []))
    unresolved.extend([
        "Architecture counts (contactors, fuses, harness and LV loads) require an electrical schematic.",
        "Stock pumps/fans/radiators have no matched operating-point curves in this catalogue.",
        "Motors, certification and full avionics are excluded; rotor/hub is a rough custom allowance."])

    def total(selected_rows: list[dict[str, Any]]) -> dict[str, float]:
        return {k: round(sum(r["subtotal_eur"][k] for r in selected_rows), 2) for k in SCENARIOS}

    scopes = {s: total([r for r in rows if r["scope"] == s]) for s in ("airborne", "ground", "labour", "nre")}
    subtotal = total(rows)
    grand_total = {k: round(v * (1 + cfg["contingency_fraction"]), 2) for k, v in subtotal.items()}
    published = sum(r["subtotal_eur"]["base"] for r in rows
                    if r["quantity"] > 0 and r["price_status"] == "published")
    if cfg["strict"]:
        raise ValueError("Strict costing rejected unresolved catalogue/qualification assumptions: "
                         + "; ".join(unresolved[:5]))
    return dict(
        status="PROVISIONAL_BUDGET_ONLY", currency="EUR", tax_basis=catalog["tax_basis"],
        subtotal_eur=subtotal, contingency_fraction=cfg["contingency_fraction"], total_eur=grand_total,
        scope_totals_eur=scopes, quantities=q, rows=rows, unresolved=unresolved,
        published_price_fraction_of_base=published / subtotal["base"] if subtotal["base"] else 0.0,
        optimizer_ready=False, provisional_objective_eur=grand_total["base"],
        engineering_feasible=not design.get("issues"), catalogue_date=catalog["price_date"],
        cost_config=cfg)


def optimizer_objective(design: dict[str, Any], config: dict[str, Any] | None = None, *,
                        allow_provisional: bool = False) -> float:
    """Base-case total EUR for an optimiser; inf when the design has model issues.

    The optimiser must opt in with allow_provisional=True, because the catalogue
    prices are mostly estimates (fine for sensitivity studies, not procurement).
    """
    report = estimate_cost(design, config)
    if design.get("issues"):
        return math.inf
    if not allow_provisional:
        raise ValueError("Catalogue is provisional. Use allow_provisional=True only for budget sensitivity studies.")
    return report["provisional_objective_eur"]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m albatros.elct_cost_estimation", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("design", type=Path, help="design JSON written by python -m albatros --json")
    parser.add_argument("--config", type=Path, help="cost assumptions JSON")
    parser.add_argument("--catalog", type=Path, help="alternative product catalogue JSON")
    parser.add_argument("--out", type=Path, required=True, help="where to write the cost report JSON")
    args = parser.parse_args(argv)
    design = json.loads(args.design.read_text(encoding="utf-8"))
    report = estimate_cost(design, load_cost_config(args.config), args.catalog)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("status", "total_eur", "optimizer_ready")}, indent=2))


if __name__ == "__main__":
    main()
