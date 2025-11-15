from decimal import Decimal
from app.simulation import run
import pandas as pd


def main() -> None:
    df = pd.read_csv("Hackathon_HSY_data.csv")

    df["Time stamp"] = pd.to_datetime(df["Time stamp"], dayfirst=True, errors="raise")

    initial_water_volume_m3 = df["Water volume in tunnel V (m3)"].tolist()[0]

    dada = df[
        [
            "Time stamp",
            "Electricity price 2: normal (EUR/kWh)",
            "Electricity price 1: high (EUR/kWh)",
            "Inflow to tunnel F1 (m3/15 min)",
        ]
    ]

    dada.rename(
        columns={
            "Time stamp": "timestamp",
            "Electricity price 2: normal (EUR/kWh)": "electricity_price_eur_cent_per_kwh",
            "Electricity price 1: high (EUR/kWh)": "electricity_price_eur_cent_per_kwh_high",
            "Inflow to tunnel F1 (m3/15 min)": "inflow_to_tunnel_m3_per_15min",
        },
        inplace=True,
    )

    print(f"Initial water volume: {initial_water_volume_m3} m3")

    run(dataframe=dada, initial_water_volume_m3=Decimal(initial_water_volume_m3))


if __name__ == "__main__":
    main()
