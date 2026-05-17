from __future__ import annotations

from typing import Any

import pyomo.environ as pyo


def add_energy_dispatch_objective(model: Any) -> None:
    """Maximise wholesale energy arbitrage revenue in GBP."""

    model.objective = pyo.Objective(
        expr=sum(
            model.price_gbp_per_mwh[t]
            * (model.discharge_mw[t] - model.charge_mw[t])
            * model.duration_h[t]
            for t in model.T
        ),
        sense=pyo.maximize,
    )
