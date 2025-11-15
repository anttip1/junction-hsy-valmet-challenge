from decimal import Decimal
from pydantic import BaseModel


class SmallPump(BaseModel):
    is_active: bool

    @property
    def pump_capacity_m3_15min(self) -> Decimal:
        return Decimal("375") if self.is_active else Decimal(0)


class LargePump(BaseModel):
    is_active: bool

    @property
    def pump_capacity_m3_15min(self) -> Decimal:
        return Decimal("750") if self.is_active else Decimal(0)


class PumpState(BaseModel):
    small_pumps: list[SmallPump]
    large_pumps: list[LargePump]

    @property
    def total_suction_m3_15min(self) -> Decimal:
        small_pump_succ = Decimal(
            sum([p.pump_capacity_m3_15min for p in self.small_pumps])
        )
        large_pump_succ = Decimal(
            sum([p.pump_capacity_m3_15min for p in self.large_pumps])
        )

        return small_pump_succ + large_pump_succ
