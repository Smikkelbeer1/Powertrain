"""Matplotlib plots of a single mission or of a sweep (needs matplotlib)."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def plot_results(data: dict[str, Any] | list[dict[str, Any]], save: Path | None, show: bool,
                 x_key: str = "mtow_kg", x_label: str = "MTOW (kg)") -> None:
    """Single design -> SOC/voltage, power, temperatures, altitude vs time.
    Sweep (list)   -> range, motor mass, remaining mass and motor temperature vs x_key.
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise ValueError("Plotting requires matplotlib: python -m pip install matplotlib") from exc
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True)
    if isinstance(data, list):
        ok = [r for r in data if "parallel" in r]  # skip failed sweep points
        if not ok:
            raise ValueError("No successful sweep points to plot")
        xs = [r[x_key] for r in ok]
        for ax, key, label in [(axes[0, 0], "range_km", "Mission range (km)"),
                               (axes[0, 1], "motors_kg", "Four motors (kg)"),
                               (axes[1, 0], "remaining_kg", "Remaining MTOW (kg)"),
                               (axes[1, 1], "worst_motor_C", "All-case motor temperature (C)")]:
            ax.plot(xs, [r[key] for r in ok], "o-")
            ax.set(xlabel=x_label, ylabel=label)
            ax.grid(alpha=0.3)
    else:
        rows = data["mission_rows"]
        t = [r["time_s"] / 60 for r in rows]
        axes[0, 0].plot(t, [100 * r["min_group_soc"] for r in rows], label="weakest SOC (%)")
        axes[0, 0].set(ylabel="SOC (%)")
        right = axes[0, 0].twinx()
        right.plot(t, [r["bus_V"] for r in rows], color="tab:orange", label="bus")
        right.set_ylabel("Bus (V)")
        for key, label in [("battery_terminal_W", "Battery output"), ("shaft_W", "Shaft")]:
            axes[0, 1].plot(t, [r[key] / 1000 for r in rows], label=label)
        axes[0, 1].set_ylabel("Power (kW)")
        for key, label in [("battery_C", "Cells"), ("motor_C", "Motor"), ("inverter_C", "Inverter")]:
            axes[1, 0].plot(t, [r[key] for r in rows], label=label)
        axes[1, 0].set_ylabel("Lumped temperature (C)")
        axes[1, 1].plot(t, [r["altitude_AGL_m"] for r in rows], label="Altitude AGL")
        axes[1, 1].set_ylabel("Altitude (m)")
        for ax in axes.flat:
            ax.set_xlabel("Mission time (min)")
            ax.grid(alpha=0.3)
            ax.legend()
    if save:
        save.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save, dpi=160)
    if show:
        plt.show()
    plt.close(fig)
