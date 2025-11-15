from datetime import datetime
from decimal import Decimal
import pandas
from pydantic import BaseModel


from app.pump import Pump, PumpType, PumpState, toggle_pump
from app.util import format_duration_from_minutes

"""
TODO:

    1. Empty pool every 24h
    2. Read file and electricity prices and inflow amounts
    3. Pump activation and deactivation logic
    4. water_level_from_water_volume func
    5. implement pump efficiency / capacity/ electricity costs
    6. Output the amount of Antti's stuff (e.g. how much hynkky has costed)

"""


class SimulationState(BaseModel):
    outflow_m3_15min: Decimal
    water_volume_m3: Decimal
    pump_state: PumpState


def run_step(
    inflow_to_tunnel_m3_15min: Decimal,
    prev_outflow_m3_15min: Decimal,
    water_volume_m3: Decimal,
    pump_state: PumpState,
) -> SimulationState:
    current_water_volume = (
        water_volume_m3 + inflow_to_tunnel_m3_15min - prev_outflow_m3_15min
    )

    # Note: outflow is calculated based on old pump state, think about it!
    total_outflow_m3_15min = pump_state.total_suction_m3_15min

    new_pump_state = pump_state

    return SimulationState(
        outflow_m3_15min=total_outflow_m3_15min,
        water_volume_m3=current_water_volume,
        pump_state=new_pump_state,
    )


# TODO: implement this
def water_level_from_water_volume(water_level_m: Decimal) -> Decimal:
    # Mankel level in meters from the volume based on magic func

    return water_level_m


def change_pump_state(
    pump_state: PumpState,
    water_volume_m3: Decimal,
    timestamp: datetime,
) -> PumpState:
    upper_water_level_threshold = 100_000
    lower_water_level_threshold = 90_000

    if water_volume_m3 > upper_water_level_threshold:
        large_pumps_that_are_off = sorted(
            [
                p
                for p in pump_state.pumps
                if p.pump_type == PumpType.LARGE and not p.is_active
            ],
            key=lambda x: x.cumulative_time_minutes,
        )

        large_off_that_has_least_runtime = next(
            (p for p in large_pumps_that_are_off),
            None,
        )

        if not large_off_that_has_least_runtime:
            print("All large pumps are already active! FUCK")
            return pump_state

        set_on = toggle_pump(pump=large_off_that_has_least_runtime, timestamp=timestamp)

        new_pump_state = [
            *[p for p in pump_state.pumps if p.id is not set_on.id],
            set_on,
        ]

        return PumpState(pumps=new_pump_state)

    if water_volume_m3 < lower_water_level_threshold:
        next_large_on = next(
            (
                p
                for p in pump_state.pumps
                if p.pump_type == PumpType.LARGE and p.is_active
            ),
            None,
        )

        if not next_large_on:
            return pump_state

        set_off = toggle_pump(pump=next_large_on, timestamp=timestamp)

        new_pump_state = [
            *[p for p in pump_state.pumps if p.id is not set_off.id],
            set_off,
        ]

        return PumpState(pumps=new_pump_state)

    return pump_state


def run(dataframe: pandas.DataFrame, initial_water_volume_m3: Decimal) -> None:
    # TODO:
    # Does the initial state assume that outflow starts from zero or from an initial value?

    outflow = Decimal(0)
    water_volume_m3 = initial_water_volume_m3

    pump_state = PumpState(
        pumps=[
            Pump(id="1.1", pump_type=PumpType.SMALL, current_run_time_start=None),
            Pump(id="2.1", pump_type=PumpType.SMALL, current_run_time_start=None),
            Pump(id="2.2", pump_type=PumpType.LARGE, current_run_time_start=None),
            Pump(id="2.3", pump_type=PumpType.LARGE, current_run_time_start=None),
            Pump(id="2.4", pump_type=PumpType.LARGE, current_run_time_start=None),
            Pump(id="1.2", pump_type=PumpType.LARGE, current_run_time_start=None),
            Pump(id="1.3", pump_type=PumpType.LARGE, current_run_time_start=None),
            Pump(id="1.4", pump_type=PumpType.LARGE, current_run_time_start=None),
        ]
    )
    round_number = 0

    for _, row in dataframe.iterrows():
        altered_state = run_step(
            inflow_to_tunnel_m3_15min=Decimal(row["inflow_to_tunnel_m3_per_15min"]),  # pyright: ignore
            prev_outflow_m3_15min=outflow,
            water_volume_m3=water_volume_m3,
            pump_state=pump_state,
        )
        timestamp: pandas.Timestamp = row["timestamp"]  # pyright: ignore
        dt = timestamp.to_pydatetime()
        pump_state = change_pump_state(
            pump_state=pump_state, water_volume_m3=water_volume_m3, timestamp=dt
        )

        round_number += 1

        outflow = altered_state.outflow_m3_15min
        water_volume_m3 = altered_state.water_volume_m3

        if altered_state.water_volume_m3 > 225000:
            print("shitfuckshit")
            raise Exception("Water volume exceeded maximum limit!")

        print(round_number)
        print(f"outflow m3 15min {altered_state.outflow_m3_15min}")
        print(f"water_volume_m3  {altered_state.water_volume_m3}")

        for pump in altered_state.pump_state.pumps:
            print(
                f"ID: {pump.id}; {pump.pump_type}; Active: {pump.is_active}; Total time on: {format_duration_from_minutes(pump.cumulative_time_minutes)}"
            )

        print()
