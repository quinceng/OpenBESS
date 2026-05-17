from __future__ import annotations

import pyomo.environ as pyo

from gb_bess_revenue_stack.optimisation.constraints_energy import add_energy_dispatch_constraints
from gb_bess_revenue_stack.optimisation.inputs import DispatchInput
from gb_bess_revenue_stack.optimisation.objective import add_energy_dispatch_objective
from gb_bess_revenue_stack.optimisation.variables import add_energy_dispatch_variables


def build_energy_dispatch_model(dispatch_input: DispatchInput) -> pyo.ConcreteModel:
    """Build a deterministic energy-only BESS dispatch model without solving it."""

    model = pyo.ConcreteModel(name="energy_dispatch")
    model.T = pyo.RangeSet(0, dispatch_input.period_count - 1)
    model.SOC_INDEX = pyo.RangeSet(0, dispatch_input.period_count)
    model.duration_h = pyo.Param(
        model.T,
        initialize={period.index: period.duration_h for period in dispatch_input.periods},
    )
    model.price_gbp_per_mwh = pyo.Param(
        model.T,
        initialize={period.index: period.price_gbp_per_mwh for period in dispatch_input.periods},
    )
    model.dispatch_input = dispatch_input
    add_energy_dispatch_variables(model, dispatch_input)
    add_energy_dispatch_constraints(model, dispatch_input)
    add_energy_dispatch_objective(model)
    return model
