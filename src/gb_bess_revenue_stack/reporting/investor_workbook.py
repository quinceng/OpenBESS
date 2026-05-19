from __future__ import annotations

from datetime import UTC, datetime
from html import escape
from pathlib import Path
from typing import TypeAlias
from zipfile import ZIP_DEFLATED, ZipFile

from pydantic import BaseModel, ConfigDict, Field, field_validator

from gb_bess_revenue_stack.commercial import CommercialBessSystem
from gb_bess_revenue_stack.policies.rolling_market_stack import (
    RollingMarketStackRun,
    RollingMarketStackScenarioResult,
)
from gb_bess_revenue_stack.schemas.base import ensure_aware_utc

CellValue: TypeAlias = str | int | float | bool | datetime | None

REQUIRED_SHEETS = (
    "Summary",
    "Assumptions",
    "Solver Output",
    "Dispatch",
    "Revenue Stack",
    "Caveats",
)


class InvestorWorkbookInput(BaseModel):
    """Inputs required to build the Phase 4 investor workbook."""

    model_config = ConfigDict(extra="forbid")

    commercial_system: CommercialBessSystem
    rolling_run: RollingMarketStackRun
    scenario_results: list[RollingMarketStackScenarioResult]
    caveats: list[str]
    created_at_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))
    assumptions: dict[str, str | int | float | bool | None] = Field(default_factory=dict)

    @field_validator("created_at_utc")
    @classmethod
    def created_at_is_aware(cls, value: datetime) -> datetime:
        return ensure_aware_utc(value)


def write_investor_workbook(payload: InvestorWorkbookInput, path: str | Path) -> Path:
    """Write a minimal XLSX workbook for Phase 4 investor review."""

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheets = [
        ("Summary", _summary_rows(payload)),
        ("Assumptions", _assumption_rows(payload)),
        ("Solver Output", _solver_rows(payload)),
        ("Dispatch", _dispatch_rows(payload)),
        ("Revenue Stack", _revenue_stack_rows(payload)),
        ("Caveats", _caveat_rows(payload)),
    ]
    with ZipFile(output_path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _content_types_xml(len(sheets)))
        archive.writestr("_rels/.rels", _root_relationships_xml())
        archive.writestr("xl/workbook.xml", _workbook_xml([name for name, _rows in sheets]))
        archive.writestr("xl/_rels/workbook.xml.rels", _workbook_relationships_xml(len(sheets)))
        for index, (_name, rows) in enumerate(sheets, start=1):
            archive.writestr(f"xl/worksheets/sheet{index}.xml", _sheet_xml(rows))
    return output_path


def _summary_rows(payload: InvestorWorkbookInput) -> list[list[CellValue]]:
    system = payload.commercial_system
    run = payload.rolling_run
    return [
        ["Metric", "Value"],
        ["Created at", payload.created_at_utc],
        ["Site", system.name],
        ["Battery size", f"{system.battery_capacity_mwh:.2f} MWh"],
        ["Power rating", f"{system.inverter_power_mw:.2f} MW"],
        ["Export limit", f"{system.effective_export_limit_mw:.2f} MW"],
        ["Capex", f"GBP {system.total_capex_gbp:,.0f}"],
        ["Rolling energy revenue", run.realised_energy_revenue_gbp],
        ["Rolling EAC service revenue", run.realised_service_revenue_gbp],
        ["Rolling total revenue", run.realised_total_revenue_gbp],
        ["Final SOC", f"{run.final_soc_mwh:.2f} MWh"],
        ["Forecast model", run.forecast_model],
    ]


def _assumption_rows(payload: InvestorWorkbookInput) -> list[list[CellValue]]:
    system = payload.commercial_system
    rows: list[list[CellValue]] = [
        ["Assumption", "Value"],
        ["Commercial branch", system.branch_name],
        ["Battery capacity MWh", system.battery_capacity_mwh],
        ["Inverter power MW", system.inverter_power_mw],
        ["Site export limit MW", system.site_export_limit_mw],
        ["Effective export limit MW", system.effective_export_limit_mw],
        ["Battery capex GBP/MWh", system.battery_capex_gbp_per_mwh],
        ["Inverter capex GBP/MW", system.inverter_capex_gbp_per_mw],
        ["Installation cost GBP", system.installation_cost_gbp],
        ["Grid connection cost GBP", system.grid_connection_cost_gbp],
        ["Total capex GBP", system.total_capex_gbp],
        ["Terminal SOC policy", payload.rolling_run.terminal_soc_policy],
        ["Terminal SOC target MWh", payload.rolling_run.terminal_soc_target_mwh],
    ]
    rows.extend([key, value] for key, value in payload.assumptions.items())
    return rows


def _solver_rows(payload: InvestorWorkbookInput) -> list[list[CellValue]]:
    rows: list[list[CellValue]] = [
        ["Decision time UTC", "Termination", "Wall time seconds", "Planned revenue GBP"],
    ]
    rows.extend(
        [
            step.decision_time_utc,
            step.solver_termination_condition,
            step.solver_wall_time_seconds,
            step.planned_total_revenue_gbp,
        ]
        for step in payload.rolling_run.steps
    )
    return rows


def _dispatch_rows(payload: InvestorWorkbookInput) -> list[list[CellValue]]:
    rows: list[list[CellValue]] = [
        [
            "Decision time UTC",
            "Executed periods",
            "SOC start MWh",
            "SOC end MWh",
            "Charge MW",
            "Discharge MW",
            "Reserve up MW",
            "Reserve down MW",
            "Energy revenue GBP",
            "Service revenue GBP",
            "Total revenue GBP",
        ],
    ]
    rows.extend(
        [
            step.decision_time_utc,
            step.executed_period_count,
            step.soc_start_mwh,
            step.soc_end_mwh,
            step.executed_charge_mw,
            step.executed_discharge_mw,
            _format_reserves(step.executed_reserve_up_mw),
            _format_reserves(step.executed_reserve_down_mw),
            step.realised_energy_revenue_gbp,
            step.realised_service_revenue_gbp,
            step.realised_total_revenue_gbp,
        ]
        for step in payload.rolling_run.steps
    )
    return rows


def _revenue_stack_rows(payload: InvestorWorkbookInput) -> list[list[CellValue]]:
    rows: list[list[CellValue]] = [
        ["Component", "Value GBP"],
        ["Rolling wholesale energy", payload.rolling_run.realised_energy_revenue_gbp],
        ["Rolling EAC availability", payload.rolling_run.realised_service_revenue_gbp],
        ["Rolling total", payload.rolling_run.realised_total_revenue_gbp],
        [],
        [
            "Scenario",
            "Stress label",
            "Periods",
            "Wholesale scalar",
            "EAC scalar",
            "Energy GBP",
            "EAC GBP",
            "Total GBP",
        ],
    ]
    rows.extend(
        [
            result.name,
            result.stress_label,
            result.period_count,
            result.wholesale_price_scalar,
            result.eac_price_scalar,
            result.realised_energy_revenue_gbp,
            result.realised_service_revenue_gbp,
            result.realised_total_revenue_gbp,
        ]
        for result in payload.scenario_results
    )
    return rows


def _caveat_rows(payload: InvestorWorkbookInput) -> list[list[CellValue]]:
    rows: list[list[CellValue]] = [["Caveat"]]
    rows.extend([caveat] for caveat in payload.caveats)
    return rows


def _format_reserves(values: dict[str, float]) -> str:
    if not values:
        return ""
    return "; ".join(f"{service}: {value:.3f}" for service, value in sorted(values.items()))


def _sheet_xml(rows: list[list[CellValue]]) -> str:
    row_xml = []
    for row_index, row in enumerate(rows, start=1):
        cells = [
            _cell_xml(column_index, row_index, value)
            for column_index, value in enumerate(row, start=1)
        ]
        row_xml.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<sheetData>"
        f"{''.join(row_xml)}"
        "</sheetData>"
        "</worksheet>"
    )


def _cell_xml(column_index: int, row_index: int, value: CellValue) -> str:
    coordinate = f"{_column_name(column_index)}{row_index}"
    if value is None:
        return f'<c r="{coordinate}"/>'
    if isinstance(value, bool):
        return f'<c r="{coordinate}" t="b"><v>{1 if value else 0}</v></c>'
    if isinstance(value, int | float) and not isinstance(value, bool):
        return f'<c r="{coordinate}"><v>{value}</v></c>'
    text = _format_text(value)
    return f'<c r="{coordinate}" t="inlineStr"><is><t>{escape(text)}</t></is></c>'


def _format_text(value: CellValue) -> str:
    if isinstance(value, datetime):
        return ensure_aware_utc(value).strftime("%Y-%m-%d %H:%M UTC")
    return str(value)


def _column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _workbook_xml(sheet_names: list[str]) -> str:
    sheets = "".join(
        f'<sheet name="{escape(name)}" sheetId="{index}" r:id="rId{index}"/>'
        for index, name in enumerate(sheet_names, start=1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<sheets>{sheets}</sheets>"
        "</workbook>"
    )


def _content_types_xml(sheet_count: int) -> str:
    sheet_overrides = "".join(
        '<Override PartName="/xl/worksheets/sheet'
        f'{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.'
        'spreadsheetml.worksheet+xml"/>'
        for index in range(1, sheet_count + 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.'
        'relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.'
        'openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        f"{sheet_overrides}"
        "</Types>"
    )


def _root_relationships_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/'
        'officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )


def _workbook_relationships_xml(sheet_count: int) -> str:
    relationships = "".join(
        '<Relationship Id="rId'
        f'{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
        f'relationships/worksheet" Target="worksheets/sheet{index}.xml"/>'
        for index in range(1, sheet_count + 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f"{relationships}"
        "</Relationships>"
    )
