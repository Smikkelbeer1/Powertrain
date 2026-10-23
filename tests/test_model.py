"""Physics and consistency checks.  Run with:  python -m pytest"""
from __future__ import annotations

import math
from dataclasses import replace

from albatros import motor_family
from albatros.atmosphere import atmosphere
from albatros.balancing import balancing_report
from albatros.cooling import air_operation, design_cooling, effectiveness, thermal_step
from albatros.electrical import battery_point, electrical, ocv, section_counts
from albatros.inputs import Inputs
from albatros.mission import Segment, mission_segments
from albatros.propulsion import (drag_N, hover_constants, mtow_for_torque, prop_coefficients, propulsion,
                                 required_ratings, size_motors, solve_cruise_rotor)
from albatros.recovery import landing_recovery
from albatros.sizing import (electrical_check, emergency_checkpoints, parallel_from_mass, run_model,
                             sweep_values)
from albatros.state import State, initial_state

HOVER = Segment("hover", 1, 0)


def test_atmosphere_sea_level_and_altitude():
    rho, _, _ = atmosphere(0, 15)
    assert abs(rho - 1.225) < 0.001
    assert atmosphere(2000, 15)[0] < rho


def test_battery_power_balance():
    x = Inputs()
    current, voltage, heat, _ = battery_point(100000, 0.8, 0.798, 190, 20, x)
    assert math.isclose(current * voltage, 100000, rel_tol=1e-12)  # delivered power
    assert math.isclose(current * 190 * ocv(0.8, x.cell), 100000 + heat, rel_tol=1e-12)


def test_heat_exchanger_effectiveness_below_one():
    assert effectiveness(1000, 500, 1000) < 1


def test_vertical_climb_ends_at_rest_at_transition_height():
    vertical = [s for s in mission_segments(Inputs())
                if s.name.startswith("vertical_") and s.name != "vertical_descent"]
    last = vertical[-1]
    assert math.isclose(last.altitude(last.duration_s), 60)
    assert math.isclose(last.vertical_speed(last.duration_s), 0, abs_tol=1e-12)


def test_hover_power_scales_with_mass_to_1_5():
    x = Inputs()
    p1 = sum(r.shaft_W for r in propulsion(x, HOVER, 0, [0.0] * 4))
    heavy = replace(x, aircraft=replace(x.aircraft, mass_kg=1500))
    p2 = sum(r.shaft_W for r in propulsion(heavy, HOVER, 0, [0.0] * 4))
    assert math.isclose(p2 / p1, 2 ** 1.5, rel_tol=1e-12)


def test_emergency_pair_carries_full_weight():
    x = Inputs()
    r = propulsion(x, Segment("emergency", 30, 60, active=(0, 3)), 0, [0.0] * 4)
    assert r[1].shaft_W == r[2].shaft_W == 0
    assert math.isclose(r[0].thrust_N + r[3].thrust_N, 750 * 9.80665)


def test_balancing_time_scales_with_parallel_count():
    x = Inputs()
    t1 = balancing_report(x, 190, 10)["estimated_ground_hours"]
    t2 = balancing_report(x, 190, 20)["estimated_ground_hours"]
    assert math.isclose(t2, 2 * t1)


def test_sweep_values_float_steps():
    assert sweep_values(300, 300.5, 0.25) == [300, 300.25, 300.5]


def test_thermal_step_conserves_energy():
    x = Inputs()
    motors = size_motors(x, mission_segments(x))
    loops = design_cooling(x, 190, 38, motors)
    state = initial_state(x)
    point = electrical(x, propulsion(x, HOVER, 0, motors.power_W), 0,
                       state.soc_mean, state.soc_min, 190, 38)

    def stored_J(st: State) -> float:
        return (sum(t * m * x.motor.cp_J_kgK for t, m in zip(st.motor_C, motors.mass_kg))
                + sum(st.inverter_C) * x.inverter.mass_each_kg * x.inverter.cp_J_kgK
                + sum(t * n * 38 * x.cell.mass_kg * x.cell.cp_J_kgK
                      for t, n in zip(st.battery_C, section_counts(190)))
                + sum(t * l.coolant_kg * x.cooling.coolant_cp_J_kgK for t, l in zip(st.coolant_C, loops)))

    before = stored_J(state)
    qrad, qrev = thermal_step(x, state, point, loops, motors, 190, 38, 25.0, 0.1)
    generated = (point.heat_W + qrev + sum(d.motor_heat_W + d.inverter_heat_W for d in point.drives)
                 + sum(l.pump_W for l in loops))
    assert math.isclose(stored_J(state) - before, (generated - qrad) * 0.1, rel_tol=1e-8)


def test_fan_limited_airflow_at_altitude():
    x = Inputs()
    motors = size_motors(x, mission_segments(x))
    loops = design_cooling(x, 190, 38, motors)
    _, _, fractions, _ = air_operation(x, loops, 6000, 0)
    assert min(fractions) < 1  # a limited fan must reduce airflow, not invent cooling


# --- New features ---------------------------------------------------------

def test_motor_mass_torque_fit_is_invertible():
    assert math.isclose(motor_family.torque_from_mass(motor_family.mass_from_torque(400)), 400)
    assert 0.9 < motor_family.R2_LOG <= 1


def test_family_motor_mass_follows_required_torque():
    x = Inputs()
    motors = size_motors(x, mission_segments(x))
    for q, m in zip(motors.torque_Nm, motors.mass_kg):
        assert math.isclose(m, motor_family.mass_from_torque(q))


def test_torque_driven_mode_hits_given_torque():
    x = Inputs()
    x.motor.peak_torque_Nm = 600
    mtow = mtow_for_torque(x)
    trial = replace(x, aircraft=replace(x.aircraft, mass_kg=mtow))
    _, torque = required_ratings(trial, mission_segments(trial))
    assert math.isclose(max(torque), 600, rel_tol=1e-6)


def test_coefficient_hover_matches_figure_of_merit_formula():
    x = Inputs()
    x.propeller.model = "coefficients"
    ct, fm = hover_constants(x.propeller)
    for r, d in zip(propulsion(x, HOVER, 0, [0.0] * 4), x.aircraft.diameters_m):
        rho = atmosphere(0, x.cooling.sea_level_ambient_C)[0]
        n = r.rpm / 60
        assert math.isclose(r.thrust_N, ct * rho * n ** 2 * d ** 4)  # CT definition
        assert math.isclose(r.shaft_W, x.propeller.CP[0] * rho * n ** 3 * d ** 5)  # CP definition


def test_cruise_rotor_solution_matches_table():
    p = Inputs().propeller
    rho, speed, d, thrust = 1.1, 65.0, 1.47, 300.0
    rpm, power = solve_cruise_rotor(p, thrust, speed, d, rho)
    n = rpm / 60
    ct, cp = prop_coefficients(p, speed / (n * d))
    assert math.isclose(ct * rho * n ** 2 * d ** 4, thrust, rel_tol=1e-6)
    assert math.isclose(cp * rho * n ** 3 * d ** 5, power)
    assert thrust * speed / power < 1  # propeller efficiency must stay below 1


def test_drag_polar_reduces_to_lift_drag_shape():
    x = Inputs()
    W = 750 * 9.80665
    assert math.isclose(drag_N(x, W, 1.2, 65), W / x.aerodynamics.lift_drag)
    x.aerodynamics.drag_model = "polar"
    # Induced drag falls with speed^2, parasite drag rises: there is a minimum.
    d_slow, d_mid, d_fast = (drag_N(x, W, 1.2, v) for v in (25, 45, 120))
    assert d_mid < d_slow and d_mid < d_fast


def test_landing_recovery_turn_back_after_climb():
    x = Inputs()
    design = run_model(x)
    r = landing_recovery(x, design, max_cruise_s=0, margin_C=5)
    assert [t["cruise_s"] for t in r["trials"]] == [0]
    assert r["landing_phases"][-1] == "vertical_descent"
    assert "cruise" not in r["prefix_phases"]
    # An impossible margin (beyond every limit) must fail, never pass.
    assert not landing_recovery(x, design, max_cruise_s=0, margin_C=500)["feasible"]


def test_volume_budget_and_integrated_inverter():
    x = Inputs()
    r = run_model(x)
    v = r["volumes_L"]
    # Battery envelope = bare cell volume / fill fraction; total = sum of parts.
    assert math.isclose(v["battery_packs"], r["battery_bare_volume_L"] / x.battery.volume_fill_fraction)
    assert math.isclose(r["total_volume_L"], sum(v.values()))
    assert math.isclose(v["radiator"], sum(l["core_m3"] for l in r["cooling_loops"]) * 1000)
    assert math.isclose(v["motors"], r["motors_total_kg"] / x.motor.density_kg_m3 * 1000)
    # Integrated inverter: no separate mass, volume or cold plate.
    assert r["inverters_total_kg"] == 0 and v["inverters"] == 0
    x.inverter.integrated_in_motor = False
    separate = run_model(x)
    assert math.isclose(separate["inverters_total_kg"], 4 * x.inverter.mass_each_kg)
    assert separate["accounted_subsystems_kg"] > r["accounted_subsystems_kg"]


def test_propwash_credit_reduces_fans_not_radiators():
    x = Inputs()
    motors = size_motors(x, mission_segments(x))
    base = design_cooling(x, 190, 25, motors)
    x.cooling.hover_propwash_pressure_Pa = 400  # downwash delivers 400 of the 500 Pa
    helped = design_cooling(x, 190, 25, motors)
    for b, h in zip(base, helped):
        assert math.isclose(h.fan_design_dp_Pa, 100)
        assert h.fan_rating_W < 0.25 * b.fan_rating_W  # ~1/5 of the pressure, slightly less heat
        assert math.isclose(h.core_m3, b.core_m3, rel_tol=0.05)  # radiator still needed
    # In hover the downwash now helps; in cruise (not rotor-borne) it does not.
    hover_fan = air_operation(x, helped, 60, 0, rotor_borne=True)[0]
    no_help = air_operation(x, helped, 60, 0, rotor_borne=False)[0]
    assert hover_fan < no_help


def test_fan_volume_rules():
    x = Inputs()
    motors = size_motors(x, mission_segments(x))
    full = design_cooling(x, 190, 25, motors)
    x.cooling.fan_face_coverage = 0.5
    half = design_cooling(x, 190, 25, motors)
    assert math.isclose(sum(l.volumes_L["fan"] for l in half), 0.5 * sum(l.volumes_L["fan"] for l in full))
    x.cooling.fan_volume_L_per_kW = 4.0  # power rule overrides the geometry rule
    by_power = design_cooling(x, 190, 25, motors)
    for l in by_power:
        assert math.isclose(l.volumes_L["fan"], 4.0 * l.fan_rating_W / 1000)


def test_battery_mass_fraction_fits_largest_pack():
    x = Inputs()  # default: battery mass fraction mode
    budget = x.battery.mass_fraction * x.aircraft.mass_kg
    np, got_budget = parallel_from_mass(x, 190)
    assert math.isclose(got_budget, budget)

    def pack_kg(n: int) -> float:  # same formula as the mass budget in run_model
        return (190 * n * x.cell.mass_kg * (1 + x.battery.noncooling_packaging_fraction)
                + balancing_report(x, 190, n)["hardware_mass_kg"])

    assert pack_kg(np) <= budget < pack_kg(np + 1)  # largest Np that still fits


def test_max_cruise_is_the_limit():
    x = Inputs()
    r = run_model(x)
    assert r["sizing_mode"].startswith("battery mass fraction")
    assert r["battery_dry_with_BMS_kg"] <= r["battery_mass_budget_kg"]
    assert r["cruise_limit"]  # a little longer cruise must fail
    # The found cruise passes; 10 s more fails (search resolution is 1 s).
    motors = size_motors(x, mission_segments(x))
    for extra, should_pass in ((0, True), (10, False)):
        trial = Inputs()
        trial.mission.cruise_s = r["cruise_s"] + extra
        reasons = electrical_check(trial, r["series"], r["parallel"], motors, mission_segments(trial))
        assert (not reasons) == should_pass
    assert r["range_km"] > r["cruise_s"] * x.aircraft.cruise_kmh / 3600  # cruise + climb/descent


def test_mass_fraction_zero_gives_automatic_sizing():
    x = Inputs()
    x.battery.mass_fraction = 0
    r = run_model(x)
    assert r["sizing_mode"] == "automatic electrical sizing"
    assert r["cruise_s"] == x.mission.cruise_s and r["battery_mass_budget_kg"] is None


def test_emergency_rules_ground_checkpoints_and_current_limit():
    x = Inputs()
    checkpoints = [("departure", 0.0, None), ("after_cruise", 600.0, None),
                   ("after_vertical_descent", 0.0, None)]
    assert [c[0] for c in emergency_checkpoints(x, checkpoints)] == ["after_cruise"]
    x.aircraft.emergency_on_ground = True
    assert len(emergency_checkpoints(x, checkpoints)) == 3

    # 750 kg, 19P, 20 min cruise: the emergency exceeds 45 A per cell, but a
    # higher short-term emergency limit lets it pass. Normal flight still uses 45 A.
    x = Inputs()
    x.mission.cruise_s = 1200
    motors = size_motors(x, mission_segments(x))
    strict = electrical_check(x, 190, 19, motors, mission_segments(x))
    assert any(r.startswith("cell current (emergency") for r in strict)
    x.cell.emergency_max_current_A = 60
    assert electrical_check(x, 190, 19, motors, mission_segments(x)) == []
