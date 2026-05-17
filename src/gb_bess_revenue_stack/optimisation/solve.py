from __future__ import annotations

import time
from typing import Any

import pyomo.environ as pyo
from pydantic import BaseModel, ConfigDict, Field

from gb_bess_revenue_stack.config.models import SolverConfig


class OptimisationSolveError(RuntimeError):
    """Raised when the optimisation solver cannot produce an acceptable solution."""


class SolverDiagnostics(BaseModel):
    """Solver metadata recorded in run manifests and results."""

    model_config = ConfigDict(extra="forbid")

    solver_name: str
    status: str
    termination_condition: str
    objective_value: float
    wall_time_seconds: float = Field(ge=0)
    time_limit_seconds: int
    mip_gap: float
    best_bound: float | None = None


def solve_dispatch_model(
    model: Any,
    solver_config: SolverConfig | None = None,
) -> SolverDiagnostics:
    """Solve a Pyomo energy-dispatch model with HiGHS by default."""

    config = solver_config or SolverConfig()
    solver_name = "appsi_highs" if config.name in {"highs", "appsi_highs"} else config.name
    solver = pyo.SolverFactory(solver_name)
    if not solver.available(exception_flag=False):
        msg = f"Solver {solver_name!r} is not available."
        raise OptimisationSolveError(msg)
    _configure_solver(solver, config)
    start = time.perf_counter()
    results = solver.solve(model)
    wall_time = time.perf_counter() - start
    status = str(results.solver.status)
    termination = str(results.solver.termination_condition)
    if "optimal" not in termination.lower():
        msg = f"Dispatch solve failed: status={status}, termination={termination}."
        raise OptimisationSolveError(msg)
    return SolverDiagnostics(
        solver_name=solver_name,
        status=status,
        termination_condition=termination,
        objective_value=float(pyo.value(model.objective)),
        wall_time_seconds=wall_time,
        time_limit_seconds=config.time_limit_seconds,
        mip_gap=config.mip_gap,
        best_bound=_best_bound(results),
    )


def _configure_solver(solver: Any, config: SolverConfig) -> None:
    solver_config = getattr(solver, "config", None)
    if solver_config is not None:
        if hasattr(solver_config, "time_limit"):
            solver_config.time_limit = config.time_limit_seconds
        if hasattr(solver_config, "mip_gap"):
            solver_config.mip_gap = config.mip_gap
        return
    options = getattr(solver, "options", None)
    if options is not None:
        options["time_limit"] = config.time_limit_seconds
        options["mip_rel_gap"] = config.mip_gap


def _best_bound(results: Any) -> float | None:
    bound = getattr(results.problem, "lower_bound", None)
    if bound is None:
        bound = getattr(results.problem, "upper_bound", None)
    try:
        return None if bound is None else float(bound)
    except (TypeError, ValueError):
        return None
