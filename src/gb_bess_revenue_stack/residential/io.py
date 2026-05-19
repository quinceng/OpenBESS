from __future__ import annotations

import csv
from pathlib import Path

from gb_bess_revenue_stack.residential.profiles import (
    ResidentialHouseholdInterval,
    ResidentialTariffPeriod,
    ResidentialTariffSchedule,
    validate_household_intervals,
)
from gb_bess_revenue_stack.schemas.base import parse_source_datetime


def load_household_profile_csv(path: str | Path) -> list[ResidentialHouseholdInterval]:
    """Load household load/PV intervals from a CSV file."""

    with Path(path).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    intervals = [
        ResidentialHouseholdInterval(
            delivery_start_utc=parse_source_datetime(row["delivery_start_utc"]),
            delivery_end_utc=parse_source_datetime(row["delivery_end_utc"]),
            load_kwh=float(row["load_kwh"]),
            pv_generation_kwh=float(row["pv_generation_kwh"]),
        )
        for row in rows
    ]
    return validate_household_intervals(intervals)


def load_tariff_csv(path: str | Path) -> ResidentialTariffSchedule:
    """Load residential import/export tariff periods from a CSV file."""

    with Path(path).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return ResidentialTariffSchedule(
        periods=tuple(
            ResidentialTariffPeriod(
                valid_from_utc=parse_source_datetime(row["valid_from_utc"]),
                valid_to_utc=parse_source_datetime(row["valid_to_utc"]),
                import_rate_gbp_per_kwh=float(row["import_rate_gbp_per_kwh"]),
                export_rate_gbp_per_kwh=float(row["export_rate_gbp_per_kwh"]),
                standing_charge_gbp_per_day=float(row.get("standing_charge_gbp_per_day") or 0),
            )
            for row in rows
        )
    )
