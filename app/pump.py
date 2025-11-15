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

    def capacity_m3_15min_at_level(self, water_level_m: float) -> Decimal:
        if not self.is_active:
            return Decimal(0)

        L2 = 30.0  # m, fixed plant-side level from assignment
        head_m = max(L2 - float(water_level_m), 1.0)  # avoid zero/negative head
        

        q_m3_per_h = self._flow_from_head(head_m)
        return Decimal(q_m3_per_h / 4.0)

    def _flow_from_head(self, head_m: float) -> float:
        if self.pump_type == PumpType.LARGE:
            # Example points: (head [m], flow [m3/h])
            curve = [
                (15.0, 3000.0),
                (30.0, 2000.0)
            ]
        else:
            curve = [
                (15.0, 1500.0),
                (30.0, 1000.0),
            ]

        heads = [h for h, _ in curve]
        flows = [q for _, q in curve]

        # Clamp head into the curve range
        if head_m <= heads[0]:
            return flows[0]
        if head_m >= heads[-1]:
            return flows[-1]

        # Linear interpolation between nearest points
        for (h1, q1), (h2, q2) in zip(curve, curve[1:]):
            if h1 <= head_m <= h2:
                alpha = (head_m - h1) / (h2 - h1)
                return q1 + alpha * (q2 - q1)

        # Fallback
        return flows[-1]

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
            Decimal("400") if self.pump_type == PumpType.LARGE else Decimal("250")
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

    def total_suction_m3_15min(self, water_level_m: float) -> Decimal:
        return Decimal(
            sum(p.capacity_m3_15min_at_level(water_level_m) for p in self.pumps)
        )
