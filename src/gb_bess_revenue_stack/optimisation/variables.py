from __future__ import annotations

from typing import Any

import pyomo.environ as pyo

from gb_bess_revenue_stack.optimisation.inputs import DispatchInput


def add_energy_dispatch_variables(model: Any, dispatch_input: DispatchInput) -> None:
    """Add MW/MWh decision variables to a Pyomo model."""

    model.charge_mw = pyo.Var(model.T, domain=pyo.NonNegativeReals)
    model.discharge_mw = pyo.Var(model.T, domain=pyo.NonNegativeReals)
    model.soc_mwh = pyo.Var(
        model.SOC_INDEX,
        domain=pyo.NonNegativeReals,
        bounds=(dispatch_input.soc_min_mwh, dispatch_input.soc_max_mwh),
    )
    if dispatch_input.binary_dispatch:
        model.is_discharging = pyo.Var(model.T, domain=pyo.Binary)
