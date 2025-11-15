from datetime import datetime
from decimal import Decimal
from enum import Enum
from pydantic import BaseModel


"""

TODO:
    - powah latah
    - millon polkastaan kayntiin (maailman tappiin)
    - 2h limitti harveli
    - 24h tyhjennys
"""


class PumpActivation(BaseModel):
    start_time: datetime
    end_time: datetime


class PumpType(str, Enum):
    SMALL = "small"
    LARGE = "large"


class Pump(BaseModel):
    id: str
    pump_type: PumpType

    # this is ste is pump is currently running, it is None if pump is off
    current_run_time_start: datetime | None
    activation_times: list[PumpActivation] = []

    @property
    def is_active(self) -> bool:
        return self.current_run_time_start is not None

    @property
    def pump_capacity_m3_15min(self) -> Decimal:
        pump_on_capacity = (
            Decimal("750") if self.pump_type == PumpType.LARGE else Decimal("375")
        )

        return pump_on_capacity if self.is_active else Decimal(0)

    @property
    def cumulative_time_minutes(self) -> int:
        return int(
            sum(
                (t.end_time - t.start_time).total_seconds()
                for t in self.activation_times
            )
            / 60
        )

    @property
    def current_power_kw(self) -> Decimal:
        power_kw = (
            Decimal("350") if self.pump_type == PumpType.LARGE else Decimal("200")
        )
        return power_kw if self.is_active else Decimal(0)


def toggle_pump(pump: Pump, timestamp: datetime) -> Pump:
    # Set pump off
    if pump.current_run_time_start:
        latest_activation_start = pump.current_run_time_start

        return Pump(
            id=pump.id,
            pump_type=pump.pump_type,
            current_run_time_start=None,
            activation_times=[
                *pump.activation_times,
                PumpActivation(start_time=latest_activation_start, end_time=timestamp),
            ],
        )

    # Set pump on
    return Pump(
        id=pump.id,
        pump_type=pump.pump_type,
        current_run_time_start=timestamp,
        activation_times=pump.activation_times,
    )


class PumpState(BaseModel):
    pumps: list[Pump]
    target_outflow_m3_15min: Decimal | None = None
    average_inflow_m3_15min: Decimal | None = None
    last_daily_drain_timestamp: datetime | None = None
    pending_daily_drain: bool = False

    @property
    def total_suction_m3_15min(self) -> Decimal:
        return Decimal(sum([p.pump_capacity_m3_15min for p in self.pumps]))
