from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CommercialBessSystem(BaseModel):
    """Commercial-scale BESS branch model using MW/MWh units."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    branch_name: Literal["commercial"] = "commercial"
    name: str
    battery_capacity_mwh: float = Field(gt=0)
    inverter_power_mw: float = Field(gt=0)
    site_export_limit_mw: float | None = Field(default=None, gt=0)
    effective_export_limit_mw: float = Field(default=0, ge=0)

    @model_validator(mode="after")
    def derive_effective_export_limit(self) -> CommercialBessSystem:
        export_limit = self.site_export_limit_mw
        if export_limit is None:
            export_limit = self.inverter_power_mw
        object.__setattr__(
            self,
            "effective_export_limit_mw",
            min(self.inverter_power_mw, export_limit),
        )
        return self
