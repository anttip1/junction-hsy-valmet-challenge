import csv
from datetime import datetime
from decimal import Decimal
import pandas
from pydantic import BaseModel


from app.pump import Pump, PumpType, PumpState

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


class LogEntry(BaseModel):
    timestamp: datetime
    water_volume_m3: Decimal
    inflow_to_tunnel_m3_15min: Decimal
    outflow_m3_15min: Decimal
    pump_state: PumpState
    electricity_price_eur_cent_per_kwh: Decimal


def run(dataframe: pandas.DataFrame, initial_water_volume_m3: Decimal) -> None:
    # TODO:
    # Does the initial state assume that outflow starts from zero or from an initial value?
    utcnow = datetime.now()
    outflow = Decimal(0)
    water_volume_m3 = initial_water_volume_m3

    large_pump = Pump(
        id=1, pump_type=PumpType.LARGE, current_run_time_start=datetime.now()
    )
    small_pump = Pump(id=2, pump_type=PumpType.SMALL, current_run_time_start=None)

    pump_state = PumpState(pumps=[large_pump, small_pump])

    logs: list[LogEntry] = [
        LogEntry(
            timestamp=dataframe.iloc[0]["timestamp"],
            water_volume_m3=water_volume_m3,
            inflow_to_tunnel_m3_15min=Decimal(
                dataframe.iloc[0]["inflow_to_tunnel_m3_per_15min"]
            ),
            outflow_m3_15min=outflow,
            pump_state=pump_state,
            electricity_price_eur_cent_per_kwh=Decimal(
                dataframe.iloc[0]["electricity_price_eur_cent_per_kwh"]
            ),
        )
    ]

    round_number = 0

    for _, row in dataframe[1:].iterrows():
        altered_state = run_step(
            inflow_to_tunnel_m3_15min=Decimal(
                row["inflow_to_tunnel_m3_per_15min"]
            ),  # pyright: ignore
            prev_outflow_m3_15min=outflow,
            water_volume_m3=water_volume_m3,
            pump_state=pump_state,
        )
        logs.append(
            LogEntry(
                timestamp=row["timestamp"],
                water_volume_m3=altered_state.water_volume_m3,
                outflow_m3_15min=altered_state.outflow_m3_15min,
                inflow_to_tunnel_m3_15min=Decimal(row["inflow_to_tunnel_m3_per_15min"]),
                pump_state=altered_state.pump_state,
                electricity_price_eur_cent_per_kwh=Decimal(
                    row["electricity_price_eur_cent_per_kwh"]
                ),
            )
        )
        round_number += 1

        outflow = altered_state.outflow_m3_15min
        water_volume_m3 = altered_state.water_volume_m3

        if altered_state.water_volume_m3 > 225000:
            print("shitfuckshit")
            break

        print(round_number)
        print(altered_state)
        print()

    with open(
        f"simulation_output_{utcnow.hour}_{utcnow.minute}_{utcnow.second}.csv", "w"
    ) as filepointer:

        # Create fieldnames dynamically for all the pumps that were logged

        pump_ids = sorted(set(pump.id for log in logs for pump in log.pump_state.pumps))

        # pump_power_fieldnames = [f"pump_{pump_id}_power_kw" for pump_id in pump_ids]
        # pump_flow_fieldnames = [f"pump_{pump_id}_flow_m3_15min" for pump_id in pump_ids]

        fieldnames_and_labels = {
            "timestamp": "Time stamp",
            "water_volume_m3": "Water volume in tunnel V (m3)",
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
            "electricity_price_eur_cent_per_kwh": "Electricity price (eur cent/kWh)",
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
                "inflow_to_tunnel_m3_15min": log.inflow_to_tunnel_m3_15min,
                "outflow_m3_15min": log.outflow_m3_15min,
                "electricity_price_eur_cent_per_kwh": log.electricity_price_eur_cent_per_kwh,
            }
            for pump in log.pump_state.pumps:
                row_dict[f"pump_{pump.id}_power_kw"] = pump.current_power_kw
                row_dict[f"pump_{pump.id}_flow_m3_15min"] = pump.pump_capacity_m3_15min
            csv_dictwriter.writerow(row_dict)
