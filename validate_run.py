import pandas as pd


def get_pump_power_columns(df: pd.DataFrame) -> list[str]:
    return [
        column_name for column_name in df.columns if "Pump efficiency" in column_name
    ]


def calculate_one_pump_runtime_hours(
    df: pd.DataFrame, pump_power_column: str, time_step_hours: float
) -> float:
    """Return runtime for a single pump based on non-zero power readings."""
    is_running = df[pump_power_column].fillna(0) > 0
    return is_running.sum() * time_step_hours


def calculate_all_pumps_runtime_hours(df: pd.DataFrame) -> None:
    pump_power_columns = get_pump_power_columns(df)
    time_step_hours = 0.25  # 15-minute intervals
    print("Pump runtimes (hours):")
    for column_name in pump_power_columns:
        runtime_hours = calculate_one_pump_runtime_hours(
            df, column_name, time_step_hours
        )
        print(
            f"\t{column_name.replace('Pump efficiency', 'Pump').replace('(kW)', '')}: {runtime_hours:,.2f} h"
        )


def calculate_energy_costs(df: pd.DataFrame) -> None:

    pump_power_columns = get_pump_power_columns(df)

    electricity_price_high_column_name = "Electricity price 1: high (EUR/kWh)"  # The prices are actually in EUR cent/kWh. The label is wrong
    electricity_price_normal_column_name = "Electricity price 2: normal (EUR/kWh)"

    time_step_hours = 0.25  # 15-minute intervals

    # Total electrical power drawn by pumps per timestep (kW)
    total_power_kw = df[pump_power_columns].sum(axis=1)

    # Convert to energy by multiplying with timestep duration (kWh)
    energy_kwh_per_step = total_power_kw * time_step_hours

    total_energy_kwh = energy_kwh_per_step.sum()

    # Convert tariff columns from EUR cent/kWh to EUR/kWh before multiplying
    high_tariff_eur_per_kwh = df[electricity_price_high_column_name] / 100.0
    normal_tariff_eur_per_kwh = df[electricity_price_normal_column_name] / 100.0

    total_cost_high_eur = (energy_kwh_per_step * high_tariff_eur_per_kwh).sum()
    total_cost_normal_eur = (energy_kwh_per_step * normal_tariff_eur_per_kwh).sum()

    print(f"Total energy consumption: {total_energy_kwh:,.2f} kWh")
    print(f"Total energy cost at high tariff: {total_cost_high_eur:,.2f} EUR")
    print(f"Total energy cost at normal tariff: {total_cost_normal_eur:,.2f} EUR")


def calculate_power_draw_extremes(df: pd.DataFrame) -> None:
    pump_power_columns = get_pump_power_columns(df)
    total_power_kw = df[pump_power_columns].sum(axis=1)
    max_power_kw = total_power_kw.max()
    max_power_timestamp = df.loc[total_power_kw.idxmax(), "Time stamp"]
    min_power_kw = total_power_kw.min()
    min_power_timestamp = df.loc[total_power_kw.idxmin(), "Time stamp"]
    print(f"Maximum total power draw: {max_power_kw:,.2f} kW at {max_power_timestamp}")
    print(f"Minimum total power draw: {min_power_kw:,.2f} kW at {min_power_timestamp}")


def main(file_path: str) -> None:
    df = pd.read_csv(file_path)

    calculate_energy_costs(df)

    calculate_all_pumps_runtime_hours(df)

    calculate_power_draw_extremes(df)


if __name__ == "__main__":
    main("Hackathon_HSY_data.csv")
