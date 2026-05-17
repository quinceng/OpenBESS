from __future__ import annotations

from typing import Any

import pyomo.environ as pyo

from gb_bess_revenue_stack.optimisation.inputs import DispatchInput


def add_energy_dispatch_constraints(model: Any, dispatch_input: DispatchInput) -> None:
    """Add energy balance, power bounds and terminal SoC constraints.

    Units: charge/discharge are AC MW, duration is hours and SoC is internal MWh.
    """

    model.initial_soc_constraint = pyo.Constraint(
        expr=model.soc_mwh[0] == dispatch_input.initial_soc_mwh
    )

    def energy_balance_rule(model: Any, t: int) -> Any:
        return (
            model.soc_mwh[t + 1]
            == model.soc_mwh[t]
            + dispatch_input.eta_charge * model.charge_mw[t] * model.duration_h[t]
            - model.discharge_mw[t] * model.duration_h[t] / dispatch_input.eta_discharge
        )

    model.energy_balance = pyo.Constraint(model.T, rule=energy_balance_rule)

    def charge_limit_rule(model: Any, t: int) -> Any:
        return model.charge_mw[t] <= dispatch_input.p_import_max_mw

    def discharge_limit_rule(model: Any, t: int) -> Any:
        return model.discharge_mw[t] <= dispatch_input.p_export_max_mw

    model.charge_limit = pyo.Constraint(model.T, rule=charge_limit_rule)
    model.discharge_limit = pyo.Constraint(model.T, rule=discharge_limit_rule)

    if dispatch_input.binary_dispatch:

        def binary_charge_limit_rule(model: Any, t: int) -> Any:
            return model.charge_mw[t] <= dispatch_input.p_import_max_mw * (
                1 - model.is_discharging[t]
            )

        def binary_discharge_limit_rule(model: Any, t: int) -> Any:
            return model.discharge_mw[t] <= dispatch_input.p_export_max_mw * model.is_discharging[t]

        model.binary_charge_limit = pyo.Constraint(model.T, rule=binary_charge_limit_rule)
        model.binary_discharge_limit = pyo.Constraint(model.T, rule=binary_discharge_limit_rule)

    if dispatch_input.terminal_soc_policy == "cyclic":
        model.terminal_soc_constraint = pyo.Constraint(
            expr=model.soc_mwh[dispatch_input.period_count] == dispatch_input.initial_soc_mwh
        )
