"""All model inputs, grouped by WHO provides them.

Every number the model uses lives in one of the dataclasses below. You can
either edit the defaults here, or (better) write them to a JSON file with
``python -m albatros --write-config my_inputs.json``, edit that file and run
with ``--config my_inputs.json``. Command-line flags override the JSON file.

The file is split in two parts:

PART A - DEPARTMENT INPUTS (delivered by other teams, do not "design" these)
    Aircraft       MTOW, rotor layout, cruise speed, emergency assumptions
    Aerodynamics   drag (either a single L/D or a drag polar)
    Propeller      hover figure of merit / cruise efficiency, OR CT/CP tables
    Mission        the flight profile

PART B - POWERTRAIN DESIGN CHOICES (chosen by the powertrain team)
    Motor          motor sizing rule (HPDM family fit or fixed mass), efficiency
    Cell           battery cell data sheet values
    Battery        pack voltage window, SOC limits, packaging
    Balancing      passive BMS balancing hardware
    Inverter       motor drive (inverter) losses
    Auxiliaries    avionics / flight computers / actuators
    Cooling        liquid cooling loops, radiators, pumps, fans

Units are always in the field name: _kg, _m, _s, _W, _V, _A, _C (deg Celsius),
_K (temperature DIFFERENCE), _Pa, _Nm, etc.  Rotor order everywhere is
(inner_L, inner_R, outer_L, outer_R) = indices (0, 1, 2, 3).
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Rotor names, in the order used for every per-rotor tuple/list in the model.
NAMES = ("inner_L", "inner_R", "outer_L", "outer_R")
ALL = (0, 1, 2, 3)

# =============================================================================
# PART A - DEPARTMENT INPUTS
# =============================================================================


@dataclass
class Aircraft:
    """Overall aircraft data (from the aircraft design / configuration team)."""
    # Maximum take-off mass. THIS is the main design variable we sweep/optimise.
    # In torque-driven mode (Motor.peak_torque_Nm > 0) this value is ignored and
    # the model instead finds the MTOW that the chosen motor torque can carry.
    mass_kg: float = 750.0
    diameters_m: tuple[float, ...] = (1.47, 1.47, 1.04, 1.04)  # per rotor
    cruise_kmh: float = 234.0
    # One-motor-pair emergency: which rotors survive. Each pair must contain one
    # inner (0/1) and one outer (2/3) rotor. These are ASSUMED controllable pairs.
    emergency_pairs: tuple[tuple[int, int], ...] = ((0, 3), (1, 2))
    emergency_s: float = 30.0  # duration of the two-rotor emergency hover
    # False: only start emergencies while airborne (skip the checkpoints at
    # 0 m: before take-off, take-off hover at ground level, after landing).
    emergency_on_ground: bool = False
    emergency_inner_thrust_fraction: float = 0.50  # share of weight on the inner rotor
    # Normal hover thrust split. 0 = split in proportion to rotor disc area.
    normal_inner_thrust_fraction: float = 0.0
    tip_mach_limit: float = 0.85  # screening limit only


@dataclass
class Aerodynamics:
    """Drag of the aircraft in wing-borne flight (from the aerodynamics team).

    drag_model = "lift_drag": drag = weight / lift_drag  (one constant L/D)
    drag_model = "polar":     drag = q*S*(cd0 + k_induced*CL^2), CL = W/(q*S)
                              with q = 0.5*rho*V^2, so drag changes with
                              altitude (density) and speed.
    """
    drag_model: str = "lift_drag"
    lift_drag: float = 18.0
    wing_area_m2: float = 12.0  # reference area S used by cd0 and CL (placeholder)
    cd0: float = 0.012  # zero-lift drag coefficient (placeholder, gives L/D ~18)
    k_induced: float = 0.035  # induced drag factor, = 1/(pi*AR*e) (placeholder)


@dataclass
class Propeller:
    """Rotor/propeller performance (from the propeller team).

    model = "constant": hover uses figure of merit ``hover_fm`` and thrust
        coefficient ``ct_hover``; cruise uses efficiency ``cruise_prop_eff`` at
        fixed ``cruise_rpm``.
    model = "coefficients": the tables below are used instead. The standard
        propeller definitions are used (n in REVOLUTIONS PER SECOND):
            J  = V / (n*D)                 advance ratio
            CT = T / (rho * n^2 * D^4)     thrust coefficient
            CP = P / (rho * n^3 * D^5)     power coefficient
            eta = J * CT / CP              propeller efficiency
        Hover uses the J = 0 row (static CT0 and CP0). In cruise the model finds
        the rpm that gives the required thrust at the flight speed and then
        reads the power from CP, so efficiency follows from the data.
        The tables must belong to the pitch setting actually flown.

    ``cruise_rpm`` is still used to blend rpm during transitions in both modes.
    """
    model: str = "constant"
    hover_fm: float = 0.6411
    ct_hover: float = 0.10
    cruise_prop_eff: float = 0.78
    cruise_rpm: float = 3061.0
    # PLACEHOLDER table (made up, peak eta ~0.80 at J ~0.8, static FM ~0.64).
    # Replace with the propeller team's data. J must start at 0 and increase.
    J: tuple[float, ...] = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0, 1.2)
    CT: tuple[float, ...] = (0.100, 0.085, 0.070, 0.055, 0.040, 0.025, 0.010)
    CP: tuple[float, ...] = (0.0394, 0.0425, 0.0452, 0.0446, 0.0400, 0.0321, 0.0218)


@dataclass
class Mission:
    """Flight profile (from operations / flight mechanics)."""
    field_elevation_m: float = 0.0  # above mean sea level
    transition_height_m: float = 60.0  # AGL, planning input (not a compliance claim)
    vertical_speed_m_s: float = 6.0
    vertical_accel_m_s2: float = 1.0
    initial_hover_s: float = 20.0
    transition_s: float = 20.0
    # Power per motor during (back-)transition = fraction * reference power:
    #   "hover":  reference = that rotor's normal 4-rotor hover power
    #   "rating": reference = the motor's installed peak rating (original Model
    #             III; the rating is sized by the 2-motor emergency, so this is
    #             very conservative and makes transition set the battery size)
    transition_power_reference: str = "hover"
    transition_peak_fraction: float = 1.25
    cruise_height_m: float = 600.0  # AGL
    wing_climb_m_s: float = 3.0
    cruise_s: float = 3000.0  # 50 min cruise
    wing_descent_m_s: float = 3.0
    back_transition_s: float = 20.0
    back_transition_peak_fraction: float = 1.25
    landing_hover_s: float = 30.0
    vertical_descent_m_s: float = 2.0
    dt_s: float = 2.0  # simulation time step


# =============================================================================
# PART B - POWERTRAIN DESIGN CHOICES
# =============================================================================


@dataclass
class Motor:
    """Electric motor sizing and thermal data.

    Two ways to choose the MAIN input of the whole model:
      * peak_torque_Nm == 0 (default) -> MTOW-driven. The model computes the
        torque every rotor needs for Aircraft.mass_kg, and sizes the motor.
      * peak_torque_Nm  > 0 -> TORQUE-driven. All four motors get this peak
        torque; the model searches the largest MTOW they can carry.

    mass_model = "family": motor mass from the HPDM fit  m = a * T_peak^b
                           (see albatros/motor_family.py)
    mass_model = "fixed":  motor mass taken from mass_each_kg
    """
    peak_torque_Nm: float = 0.0
    mass_model: str = "family"
    mass_each_kg: tuple[float, ...] = (40.0, 40.0, 40.0, 40.0)  # only for "fixed"
    efficiency: float = 0.90  # motor only (inverter losses are in Inverter)
    rating_margin: float = 1.10  # required peak power/torque is multiplied by this
    peak_kW: tuple[float, ...] = (0.0, 0.0, 0.0, 0.0)  # 0 = derive from mission
    pole_pairs: int = 5
    electrical_Hz_limit: float = 2000.0  # assumed drive capability, NOT PWM frequency
    cp_J_kgK: float = 500.0  # specific heat of the motor (thermal mass)
    to_coolant_W_K: float = 600.0  # UA from windings to coolant
    limit_C: float = 120.0
    # Average density of the motor envelope (incl. integrated inverter), used
    # only for the volume budget: volume = mass / density. PLACEHOLDER
    # (~3500 kg/m^3 is typical for compact axial-flux motors).
    density_kg_m3: float = 3500.0


@dataclass
class Cell:
    """Battery cell. Defaults are P45B-like 21700 values (inherited assumptions).

    resistance_ohm is an ASSUMED constant DC resistance, not a measured map.
    """
    name: str = "P45B-like 21700 (inherited assumptions)"
    form: str = "cylindrical"  # cylindrical, pouch, prismatic (affects geometry only)
    capacity_Ah: float = 4.5
    nominal_V: float = 3.6
    max_V: float = 4.2
    min_V: float = 2.5
    max_current_A: float = 45.0  # continuous (datasheet, 80 degC cut-off)
    # Short-term limit during the 30 s two-rotor emergency. The P45B datasheet
    # gives no pulse rating, so it equals the continuous value until a
    # supplier figure is available.
    emergency_max_current_A: float = 45.0
    resistance_ohm: float = 0.015
    mass_kg: float = 0.070
    diameter_m: float = 0.0216
    height_m: float = 0.0702
    width_m: float = 0.100  # flat cells only
    thickness_m: float = 0.010  # flat cells only
    cp_J_kgK: float = 1000.0
    core_to_surface_K_W: float = 3.0
    contact_fraction: float = 0.30  # fraction of can surface touching the cold plate
    temp_limit_C: float = 55.0
    entropy_dU_dT_V_K: float = 0.0  # reversible heat, unknown -> disabled
    # Open-circuit voltage, equally spaced from SOC 0 to SOC 1 (placeholder table)
    ocv_V: tuple[float, ...] = (2.50, 3.15, 3.38, 3.52, 3.61, 3.69,
                               3.77, 3.85, 3.94, 4.02, 4.15)


@dataclass
class Battery:
    """Pack-level choices. Series count Ns sets voltage; parallel Np is sized."""
    bus_max_V: float = 800.0  # full-charge ceiling
    bus_min_V: float = 500.0  # lowest voltage the drives accept
    series_count: int = 0  # 0 = floor((bus_max - charge_margin) / cell.max_V)
    charge_margin_V: float = 0.0
    initial_soc: float = 1.0
    residual_soc_spread: float = 0.002  # imbalance left after ground balancing
    minimum_soc: float = 0.20  # reserve for the weakest group, also after emergency
    soh: float = 1.0  # state of health (capacity fraction)
    resistance_age_factor: float = 1.0
    noncooling_packaging_fraction: float = 0.15  # housing etc. = cells mass * this
    volume_fill_fraction: float = 0.65  # cells / pack envelope (rest: plates, BMS, housing)
    # Battery pack mass as a fraction of MTOW (cells + packaging + BMS), given
    # by the aircraft design team. The model fits the largest Np in this mass
    # and finds the LONGEST cruise it can fly. PLACEHOLDER value.
    # 0 = old behaviour: size the smallest Np for the set mission.
    mass_fraction: float = 0.40
    max_parallel: int = 250
    parallel_count: int = 0  # >0 = check this fixed Np (overrides mass_fraction)


@dataclass
class Balancing:
    """Passive balancing of series groups (generic hardware, not a chosen IC)."""
    enabled: bool = True
    initial_soc_spread: float = 0.01  # imbalance before ground balancing
    resistor_ohm: float = 42.0  # ~100 mA at 4.2 V
    switch_ohm: float = 0.10
    resistor_rating_W: float = 1.0
    resistor_usable_fraction: float = 0.50
    duty: float = 0.70
    channels_per_board: int = 16
    simultaneous_per_board: int = 4
    board_to_ambient_K_W: float = 15.0
    board_base_W: float = 0.25
    board_limit_C: float = 80.0
    board_mass_kg: float = 0.060
    channel_mass_kg: float = 0.002
    master_and_harness_kg: float = 0.60
    minimum_balancing_soc: float = 0.90


@dataclass
class Inverter:
    """Motor drive (inverter).

    integrated_in_motor = True: the inverter is built into the motor housing
        (as for most HPDM-type motors). Its mass and volume are then part of
        the motor mass/volume and are NOT counted separately, and it needs no
        separate cold plate. Its losses and temperature are still modelled,
        because the electronics still produce heat inside the motor.
    integrated_in_motor = False: separate box, mass_each_kg and
        volume_each_L are added to the budgets, plus a cold plate per loop.

    mode = "efficiency": loss = P_motor * (1/efficiency - 1)
    mode = "device":     approximate SiC two-level bridge losses (conduction,
                         switching, gate), NOT a validated device map.
    """
    integrated_in_motor: bool = True
    mode: str = "efficiency"
    efficiency: float = 0.98
    switching_Hz: float = 20000.0
    power_factor: float = 0.90
    modulation_fraction: float = 0.90
    parallel_devices_per_switch: int = 4
    rds_hot_ohm: float = 0.016
    switching_energy_J: float = 0.002  # per device Eon+Eoff at reference V and A
    reference_V: float = 800.0
    reference_A: float = 100.0
    gate_charge_C: float = 200e-9
    gate_voltage_V: float = 18.0
    control_power_W: float = 15.0
    mass_each_kg: float = 4.0  # thermal mass always; budget only if separate
    volume_each_L: float = 3.0  # only if separate (placeholder)
    cp_J_kgK: float = 800.0
    to_coolant_W_K: float = 300.0
    temp_limit_C: float = 85.0  # lumped assembly, NOT junction temperature
    device_rating_V: float = 1200.0
    voltage_usable_fraction: float = 0.80
    phase_rms_limit_A: float = 0.0  # 0 = only report the required rating


@dataclass
class Auxiliaries:
    """Low-voltage consumers powered through a DC/DC converter."""
    flight_computer_count: int = 3
    flight_computer_each_W: float = 80.0
    flight_computer_each_kg: float = 0.80
    voter_W: float = 10.0
    voter_kg: float = 0.20
    sensors_W: float = 50.0
    communications_W: float = 40.0
    bms_master_W: float = 30.0
    actuator_count: int = 8
    actuator_active_W: float = 100.0
    actuator_idle_W: float = 5.0
    actuator_cruise_duty: float = 0.10
    actuator_manoeuvre_duty: float = 0.50
    dc_dc_eff: float = 0.94
    low_voltage_V: float = 28.0
    other_avionics_actuators_kg: float = 5.0
    avionics_volume_L: float = 20.0  # all avionics boxes together (placeholder)


@dataclass
class Cooling:
    """Eight liquid loops: per pod one motor+inverter loop and one battery loop.

    Radiators are sized for ``hover_rejection_fraction`` of the hover waste heat;
    the transient simulation then shows whether temperatures stay within limits.
    """
    sea_level_ambient_C: float = 25.0
    initial_C: float = 30.0
    hover_rejection_fraction: float = 0.70
    # Coolant (water-glycol like)
    coolant_cp_J_kgK: float = 3600.0
    coolant_rho_kg_m3: float = 1050.0
    coolant_mu_Pas: float = 0.003
    coolant_k_W_mK: float = 0.42
    # Design temperature rises / targets
    prop_flow_delta_K: float = 15.0
    battery_flow_delta_K: float = 5.0
    prop_hot_coolant_design_C: float = 60.0
    battery_hot_coolant_design_C: float = 35.0
    # Hoses and pumps
    prop_line_length_m: float = 2.0
    battery_line_length_m: float = 3.0
    hose_speed_m_s: float = 1.5
    hose_min_ID_m: float = 0.006
    hose_wall_m: float = 0.0015
    hose_rho_kg_m3: float = 1200.0
    minor_loss_K: float = 10.0
    radiator_liquid_dp_Pa: float = 20000.0
    motor_jacket_dp_Pa: float = 50000.0
    pump_eff: float = 0.55
    pump_head_margin: float = 1.20
    pump_min_mass_kg: float = 0.50
    pump_mass_kg_per_kW: float = 2.0
    pump_density_kg_m3: float = 2000.0  # pump volume = pump mass / this (placeholder)
    # Air side, radiator and fan
    air_cp_J_kgK: float = 1005.0
    air_design_rise_K: float = 5.0
    radiator_air_dp_Pa: float = 500.0
    radiator_face_speed_m_s: float = 5.0
    ram_pressure_recovery: float = 0.70
    inlet_velocity_capture: float = 0.70
    fan_eff: float = 0.60
    fan_rating_margin: float = 1.25
    fan_mass_kg_per_kW: float = 1.0
    fan_depth_m: float = 0.05  # fan + shroud depth over the radiator face
    # Help from the rotor downwash in rotor-borne flight (hover, vertical
    # climb/descent, transition): the pressure the downwash delivers across
    # the radiators. The fans only make the rest. 0 = no credit (conservative).
    # Depends on where the radiators sit -> ask the aero/propeller team.
    hover_propwash_pressure_Pa: float = 0.0
    fan_face_coverage: float = 1.0  # fraction of the radiator face covered by fans
    # > 0: fan volume = this * fan rating [L per kW] instead of the geometry
    # rule (face area * coverage * depth).
    fan_volume_L_per_kW: float = 0.0
    radiator_depth_m: float = 0.06
    radiator_UA_per_m3_W_K: float = 100000.0  # ASSUMED, replace with vendor data
    radiator_envelope_density_kg_m3: float = 150.0
    radiator_header_kg: float = 0.40
    radiator_coolant_volume_fraction: float = 0.08
    pod_core_face_available_m2: float = 0.18  # space available per pod
    pod_core_volume_available_L: float = 12.0
    # Battery cold plates
    channel_wall_m: float = 0.0005
    channel_gap_m: float = 0.002
    cells_per_ribbon: int = 20
    ribbon_pitch_m: float = 0.025
    tim_thickness_m: float = 0.0005
    tim_k_W_mK: float = 2.0
    tim_rho_kg_m3: float = 2000.0
    aluminum_rho_kg_m3: float = 2700.0
    aluminum_k_W_mK: float = 180.0
    # Fixed hardware masses / volumes
    battery_manifold_each_kg: float = 0.50
    inverter_plate_each_kg: float = 0.50  # only if the inverter is a separate box
    reservoirs_each_kg: float = 0.40
    fittings_each_loop_kg: float = 0.40
    coolant_reserve_each_loop_L: float = 0.25
    jacket_and_plate_fluid_each_L: float = 0.20
    thermal_step_max_s: float = 0.50  # max sub-step for the thermal integration


@dataclass
class Inputs:
    """Everything together. JSON config files mirror this structure."""
    # Part A - department inputs
    aircraft: Aircraft = field(default_factory=Aircraft)
    aerodynamics: Aerodynamics = field(default_factory=Aerodynamics)
    propeller: Propeller = field(default_factory=Propeller)
    mission: Mission = field(default_factory=Mission)
    # Part B - powertrain design choices
    motor: Motor = field(default_factory=Motor)
    cell: Cell = field(default_factory=Cell)
    battery: Battery = field(default_factory=Battery)
    balancing: Balancing = field(default_factory=Balancing)
    inverter: Inverter = field(default_factory=Inverter)
    auxiliaries: Auxiliaries = field(default_factory=Auxiliaries)
    cooling: Cooling = field(default_factory=Cooling)
