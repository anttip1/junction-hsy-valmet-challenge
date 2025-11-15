import csv
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from itertools import product
import pandas
from pydantic import BaseModel


from app.pump import Pump, PumpType, PumpState, toggle_pump
from app.util import format_duration_from_minutes
from app.water_level import level_from_volume, V_MIN


MIN_VOLUME_REMAINING = Decimal(str(V_MIN))

"""
TODO:

    1. Empty pool every 24h
    2. Read file and electricity prices and inflow amounts
    3. Pump activation and deactivation logic
    4. water_level_from_water_volume func
    5. implement pump efficiency / capacity/ electricity costs
    6. Output the amount of Antti's stuff (e.g. how much hynkky has costed)

"""


def _round_to_increment(value: Decimal, increment: Decimal) -> Decimal:
    if increment == 0:
        return value
    return (value / increment).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    ) * increment


class SimulationState(BaseModel):
    outflow_m3_15min: Decimal
    water_volume_m3: Decimal
    water_level_from_water_volume_m: float
    pump_state: PumpState


def run_step(
    inflow_to_tunnel_m3_15min: Decimal,
    water_volume_m3: Decimal,
    pump_state: PumpState,
) -> SimulationState:
    pump_outflow_m3_15min = pump_state.total_suction_m3_15min
    max_removable = water_volume_m3 + inflow_to_tunnel_m3_15min - MIN_VOLUME_REMAINING
    if max_removable < Decimal("0"):
        max_removable = Decimal("0")
    actual_outflow_m3_15min = min(pump_outflow_m3_15min, max_removable)

    current_water_volume = (
        water_volume_m3 + inflow_to_tunnel_m3_15min - actual_outflow_m3_15min
    )
    if current_water_volume < MIN_VOLUME_REMAINING:
        current_water_volume = MIN_VOLUME_REMAINING

    new_pump_state = pump_state

    return SimulationState(
        outflow_m3_15min=actual_outflow_m3_15min,
        water_volume_m3=current_water_volume,
        water_level_from_water_volume_m=level_from_volume(float(current_water_volume)),
        pump_state=new_pump_state,
    )


# TODO: implement this
def water_level_from_water_volume(water_level_m: Decimal) -> Decimal:
    # Mankel level in meters from the volume based on magic func

    return water_level_m


class LogEntry(BaseModel):
    timestamp: datetime
    water_volume_m3: Decimal
    water_level_from_water_volume_m: float
    inflow_to_tunnel_m3_15min: Decimal
    outflow_m3_15min: Decimal
    pump_state: PumpState
    electricity_price_eur_cent_per_kwh: Decimal
    electricity_price_eur_cent_per_kwh_high: Decimal


def change_pump_state(
    pump_state: PumpState,
    water_volume_m3: Decimal,
    inflow_to_tunnel_m3_15min: Decimal,
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

        new_pump_state = [set_on if p.id == set_on.id else p for p in pump_state.pumps]

        return PumpState(pumps=new_pump_state)

    if water_volume_m3 < lower_water_level_threshold:
        if sum(p.is_active for p in pump_state.pumps) == 1:
            return pump_state

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
            set_off if p.id == set_off.id else p for p in pump_state.pumps
        ]

        return PumpState(pumps=new_pump_state)

    # Align total pump capacity with inflow to avoid over/under pumping when water level is stable.
    current_capacity = pump_state.total_suction_m3_15min
    baseline_diff = abs(inflow_to_tunnel_m3_15min - current_capacity)

    pump_capacities = [
        Decimal("750") if pump.pump_type == PumpType.LARGE else Decimal("375")
        for pump in pump_state.pumps
    ]
    current_activation_mask = [pump.is_active for pump in pump_state.pumps]

    best_mask = tuple(current_activation_mask)
    best_diff = baseline_diff
    best_toggle_count = 0
    best_active_count = sum(current_activation_mask)

    for activation_mask in product([False, True], repeat=len(pump_state.pumps)):
        capacity = sum(
            cap for cap, is_on in zip(pump_capacities, activation_mask) if is_on
        )
        diff = abs(inflow_to_tunnel_m3_15min - capacity)
        toggle_count = sum(
            1
            for current_state, desired_state in zip(
                current_activation_mask, activation_mask
            )
            if current_state != desired_state
        )
        active_count = sum(activation_mask)

        choose_candidate = False
        if diff < best_diff:
            choose_candidate = True
        elif diff == best_diff:
            if toggle_count < best_toggle_count:
                choose_candidate = True
            elif toggle_count == best_toggle_count and active_count < best_active_count:
                choose_candidate = True

        if choose_candidate:
            best_mask = activation_mask
            best_diff = diff
            best_toggle_count = toggle_count
            best_active_count = active_count

    if best_mask == tuple(current_activation_mask):
        return pump_state

    updated_pumps: list[Pump] = []
    for pump, desired_active in zip(pump_state.pumps, best_mask):
        if pump.is_active == desired_active:
            updated_pumps.append(pump)
        else:
            updated_pumps.append(toggle_pump(pump=pump, timestamp=timestamp))

    return PumpState(pumps=updated_pumps)

    return pump_state


def change_pump_state_constant_flow(
    pump_state: PumpState,
    water_volume_m3: Decimal,
    inflow_to_tunnel_m3_15min: Decimal,
    timestamp: datetime,
) -> PumpState:
    """Balance pump usage for steady outflow while enforcing operational constraints."""

    min_runtime = timedelta(hours=2)
    rain_threshold = Decimal("2000")
    flow_increment = Decimal("375")
    smoothing_alpha = Decimal("0.2")

    pump_capacities = [
        Decimal("750") if pump.pump_type == PumpType.LARGE else flow_increment
        for pump in pump_state.pumps
    ]
    max_capacity = sum(pump_capacities, Decimal("0"))
    min_non_zero_capacity = min(pump_capacities)

    level_m = Decimal(str(level_from_volume(float(water_volume_m3))))
    low_inflow = inflow_to_tunnel_m3_15min <= rain_threshold
    level_meets_drain_target = level_m <= Decimal("0.5")

    last_drain_timestamp = pump_state.last_daily_drain_timestamp
    pending_drain = pump_state.pending_daily_drain

    if level_meets_drain_target:
        last_drain_timestamp = timestamp
        pending_drain = False

    drain_due = (
        last_drain_timestamp is None
        or timestamp - last_drain_timestamp >= timedelta(hours=24)
    )

    if drain_due and not level_meets_drain_target:
        pending_drain = True

    previous_avg = pump_state.average_inflow_m3_15min
    if previous_avg is None:
        updated_average = inflow_to_tunnel_m3_15min
    else:
        updated_average = (
            previous_avg * (Decimal("1") - smoothing_alpha)
            + inflow_to_tunnel_m3_15min * smoothing_alpha
        )

    current_target = pump_state.target_outflow_m3_15min
    if current_target is None or current_target == Decimal("0"):
        current_target = pump_state.total_suction_m3_15min
    if current_target == Decimal("0"):
        current_target = min_non_zero_capacity

    if pending_drain and low_inflow and not level_meets_drain_target:
        desired_target = max_capacity
    else:
        baseline_target = _round_to_increment(updated_average, flow_increment)
        baseline_target = max(min_non_zero_capacity, min(baseline_target, max_capacity))
        delta = baseline_target - current_target
        if delta > flow_increment:
            desired_target = current_target + flow_increment
        elif delta < -flow_increment:
            desired_target = current_target - flow_increment
        else:
            desired_target = baseline_target
        desired_target = max(min_non_zero_capacity, min(desired_target, max_capacity))

    max_safe_outflow = (
        water_volume_m3 + inflow_to_tunnel_m3_15min - MIN_VOLUME_REMAINING
    )
    if max_safe_outflow < Decimal("0"):
        max_safe_outflow = Decimal("0")
    if max_safe_outflow < min_non_zero_capacity:
        max_safe_outflow = min_non_zero_capacity
    desired_target = min(desired_target, max_safe_outflow)

    current_mask = [pump.is_active for pump in pump_state.pumps]
    current_capacity = pump_state.total_suction_m3_15min

    def can_turn_on(pump: Pump) -> bool:
        if not pump.activation_times:
            return True
        last_cycle = pump.activation_times[-1]
        return timestamp - last_cycle.end_time >= min_runtime

    def can_turn_off(pump: Pump) -> bool:
        if pump.current_run_time_start is None:
            return True
        return timestamp - pump.current_run_time_start >= min_runtime

    best_mask = tuple(current_mask)
    best_score: tuple[Decimal, int, Decimal, int] | None = None

    for activation_mask in product([False, True], repeat=len(pump_state.pumps)):
        active_count = sum(activation_mask)
        if active_count == 0:
            continue

        toggle_count = 0
        allowed = True
        for pump, current, desired in zip(
            pump_state.pumps, current_mask, activation_mask
        ):
            if current == desired:
                continue
            if desired and not can_turn_on(pump):
                allowed = False
                break
            if not desired and not can_turn_off(pump):
                allowed = False
                break
            toggle_count += 1

        if not allowed:
            continue

        capacity = sum(
            cap for cap, is_on in zip(pump_capacities, activation_mask) if is_on
        )
        diff = abs(capacity - desired_target)
        smoothing_penalty = abs(capacity - current_capacity)
        score = (diff, toggle_count, smoothing_penalty, active_count)

        if best_score is None or score < best_score:
            best_score = score
            best_mask = activation_mask

    selected_pumps: list[Pump]
    if best_mask == tuple(current_mask):
        selected_pumps = list(pump_state.pumps)
    else:
        selected_pumps = []
        for pump, desired in zip(pump_state.pumps, best_mask):
            if pump.is_active == desired:
                selected_pumps.append(pump)
            else:
                selected_pumps.append(toggle_pump(pump=pump, timestamp=timestamp))

    raw_capacity = sum(cap for cap, is_on in zip(pump_capacities, best_mask) if is_on)
    selected_capacity = min(raw_capacity, max_safe_outflow)

    return PumpState(
        pumps=selected_pumps,
        target_outflow_m3_15min=selected_capacity,
        average_inflow_m3_15min=updated_average,
        last_daily_drain_timestamp=last_drain_timestamp,
        pending_daily_drain=pending_drain,
    )


def run(dataframe: pandas.DataFrame, initial_water_volume_m3: Decimal) -> None:
    # TODO:
    # Does the initial state assume that outflow starts from zero or from an initial value?
    utcnow = datetime.now()
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

    logs: list[LogEntry] = [
        LogEntry(
            timestamp=dataframe.iloc[0]["timestamp"],
            water_volume_m3=water_volume_m3,
            inflow_to_tunnel_m3_15min=Decimal(
                dataframe.iloc[0]["inflow_to_tunnel_m3_per_15min"]
            ),
            outflow_m3_15min=outflow,
            water_level_from_water_volume_m=level_from_volume(float(water_volume_m3)),
            pump_state=pump_state,
            electricity_price_eur_cent_per_kwh=Decimal(
                dataframe.iloc[0]["electricity_price_eur_cent_per_kwh"]
            ),
            electricity_price_eur_cent_per_kwh_high=Decimal(
                dataframe.iloc[0]["electricity_price_eur_cent_per_kwh_high"]
            ),
        )
    ]

    round_number = 0

    for _, row in dataframe[1:].iterrows():
        altered_state = run_step(
            inflow_to_tunnel_m3_15min=Decimal(
                row["inflow_to_tunnel_m3_per_15min"]
            ),  # pyright: ignore
            water_volume_m3=water_volume_m3,
            pump_state=pump_state,
        )

        assert (
            altered_state.water_level_from_water_volume_m < 8.00
        ), "Water level exceeded safe limit!"

        logs.append(
            LogEntry(
                timestamp=row["timestamp"],
                water_volume_m3=altered_state.water_volume_m3,
                outflow_m3_15min=altered_state.outflow_m3_15min,
                water_level_from_water_volume_m=altered_state.water_level_from_water_volume_m,
                inflow_to_tunnel_m3_15min=Decimal(row["inflow_to_tunnel_m3_per_15min"]),
                pump_state=altered_state.pump_state,
                electricity_price_eur_cent_per_kwh=Decimal(
                    row["electricity_price_eur_cent_per_kwh"]
                ),
                electricity_price_eur_cent_per_kwh_high=Decimal(
                    row["electricity_price_eur_cent_per_kwh_high"]
                ),
            )
        )
        timestamp: pandas.Timestamp = row["timestamp"]  # pyright: ignore
        dt = timestamp.to_pydatetime()
        pump_state = change_pump_state_constant_flow(
            pump_state=pump_state,
            water_volume_m3=water_volume_m3,
            inflow_to_tunnel_m3_15min=Decimal(row["inflow_to_tunnel_m3_per_15min"]),
            timestamp=dt,
        )

        round_number += 1

        outflow = altered_state.outflow_m3_15min
        water_volume_m3 = altered_state.water_volume_m3

        if altered_state.water_volume_m3 > 225000:
            print("shitfuckshit")
            break

        print(round_number)
        print(f"outflow m3 15min {altered_state.outflow_m3_15min}")
        print(f"water_volume_m3  {altered_state.water_volume_m3}")

        for pump in altered_state.pump_state.pumps:
            print(
                f"ID: {pump.id}; {pump.pump_type}; Active: {pump.is_active}; Total time on: {format_duration_from_minutes(pump.cumulative_time_minutes)}"
            )

        print()

    with open(
        f"simulation_output_{utcnow.hour}_{utcnow.minute}_{utcnow.second}.csv", "w"
    ) as filepointer:

        # Create fieldnames dynamically for all the pumps that were logged

        pump_ids = sorted(set(pump.id for log in logs for pump in log.pump_state.pumps))
        fieldnames_and_labels = {
            "timestamp": "Time stamp",
            "water_volume_m3": "Water volume in tunnel V (m3)",
            "water_level_from_water_volume_m": "Water level in tunnel L1 (m)",
            "inflow_to_tunnel_m3_15min": "Inflow to tunnel F1 (m3/15 min)",
            "outflow_m3_15min": "Outflow (m3/15 min)",
            **{
                f"pump_{pump_id}_power_kw": f"Pump efficiency {pump_id} (kW)"
                for pump_id in pump_ids
            },
            **{
                f"pump_{pump_id}_flow_m3_15min": f"Pump flow {pump_id} (m3/15 min)"
                for pump_id in pump_ids
            },
            "electricity_price_eur_cent_per_kwh": "Electricity price 2: normal (EUR/kWh)",
            "electricity_price_eur_cent_per_kwh_high": "Electricity price 1: high (EUR/kWh)",
        }

        csv_dictwriter = csv.DictWriter(
            filepointer,
            fieldnames=list(fieldnames_and_labels.keys()),
        )
        csv_dictwriter.writerow(fieldnames_and_labels)
        for log in logs:
            row_dict = {
                "timestamp": log.timestamp,
                "water_volume_m3": log.water_volume_m3,
                "water_level_from_water_volume_m": log.water_level_from_water_volume_m,
                "inflow_to_tunnel_m3_15min": log.inflow_to_tunnel_m3_15min,
                "outflow_m3_15min": log.outflow_m3_15min,
                "electricity_price_eur_cent_per_kwh": log.electricity_price_eur_cent_per_kwh,
                "electricity_price_eur_cent_per_kwh_high": log.electricity_price_eur_cent_per_kwh_high,
            }
            for pump in log.pump_state.pumps:
                row_dict[f"pump_{pump.id}_power_kw"] = pump.current_power_kw
                row_dict[f"pump_{pump.id}_flow_m3_15min"] = pump.pump_capacity_m3_15min
            csv_dictwriter.writerow(row_dict)
