from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from pydantic import BaseModel, Field

from gb_bess_revenue_stack.schemas.market import WholesalePricePoint


class QualityIssue(BaseModel):
    code: str
    severity: str
    message: str


class QualityReport(BaseModel):
    dataset: str
    row_count: int = Field(ge=0)
    duplicate_count: int = Field(ge=0)
    missing_period_count: int = Field(ge=0)
    negative_price_count: int = Field(ge=0)
    issues: list[QualityIssue] = Field(default_factory=list)

    @property
    def validation_status(self) -> str:
        return "failed" if any(issue.severity == "error" for issue in self.issues) else "passed"


def validate_wholesale_prices(records: Sequence[WholesalePricePoint]) -> QualityReport:
    issues: list[QualityIssue] = []
    negative_price_count = sum(1 for record in records if record.price_gbp_per_mwh < 0)

    seen: set[tuple[str, int, str | None]] = set()
    duplicate_count = 0
    by_date: dict[str, set[int]] = defaultdict(set)
    for record in records:
        key = (record.settlement_date, record.settlement_period, record.data_provider)
        if key in seen:
            duplicate_count += 1
            issues.append(
                QualityIssue(
                    code="duplicate_period",
                    severity="error",
                    message=f"Duplicate settlement period {key}.",
                )
            )
        seen.add(key)
        by_date[record.settlement_date].add(record.settlement_period)

    missing_period_count = 0
    for settlement_date, periods in by_date.items():
        if not periods:
            continue
        expected = set(range(min(periods), max(periods) + 1))
        missing = sorted(expected - periods)
        if missing:
            missing_period_count += len(missing)
            issues.append(
                QualityIssue(
                    code="missing_period",
                    severity="error",
                    message=f"{settlement_date} missing settlement periods {missing}.",
                )
            )

    return QualityReport(
        dataset="wholesale_price_points",
        row_count=len(records),
        duplicate_count=duplicate_count,
        missing_period_count=missing_period_count,
        negative_price_count=negative_price_count,
        issues=issues,
    )
