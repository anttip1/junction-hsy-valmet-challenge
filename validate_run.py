import argparse
import os
from statistics import pstdev

import pandas as pd
import matplotlib.pyplot as plt


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


def gini_coefficient(values: list[float]) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    total = sum(sorted_values)
    if total == 0:
        return 0.0
    n = len(sorted_values)
    weighted_sum = sum((index + 1) * value for index, value in enumerate(sorted_values))
    return (2 * weighted_sum) / (n * total) - (n + 1) / n


def count_short_runtime_events(
    df: pd.DataFrame,
    pump_power_column: str,
    time_step_hours: float,
    threshold_hours: float = 2.0,
) -> int:
    """Count contiguous on-periods shorter than the given hour threshold."""
    is_running = df[pump_power_column].fillna(0) > 0
    short_events = 0
    current_steps = 0
    for running in is_running:
        if running:
            current_steps += 1
        else:
            if 0 < current_steps * time_step_hours < threshold_hours:
                short_events += 1
            current_steps = 0
    if 0 < current_steps * time_step_hours < threshold_hours:
        short_events += 1
    return short_events


def calculate_all_pumps_runtime_hours(df: pd.DataFrame) -> None:
    pump_power_columns = get_pump_power_columns(df)
    time_step_hours = 0.25  # 15-minute intervals
    runtimes: list[tuple[str, float, int]] = []
    print("Pump runtimes (hours):")
    for column_name in pump_power_columns:
        runtime_hours = calculate_one_pump_runtime_hours(
            df, column_name, time_step_hours
        )
        short_run_count = count_short_runtime_events(df, column_name, time_step_hours)
        runtimes.append((column_name, runtime_hours, short_run_count))
        print(
            f"\t{column_name.replace('Pump efficiency', 'Pump').replace('(kW)', '')}: {runtime_hours:,.2f} h (short runs <2h: {short_run_count})"
        )
    print_runtime_balance_metrics(runtimes)


def print_runtime_balance_metrics(runtimes: list[tuple[str, float, int]]) -> None:
    runtime_values = [hours for _, hours, _ in runtimes]
    if not runtime_values:
        print("No pump runtime data available for balance metrics.")
        return
    min_hours = min(runtime_values)
    max_hours = max(runtime_values)
    range_hours = max_hours - min_hours
    print(
        f"Runtime range: {min_hours:,.2f} h – {max_hours:,.2f} h (Δ {range_hours:,.2f} h)"
    )
    if len(runtime_values) > 1:
        std_hours = pstdev(runtime_values)
    else:
        std_hours = 0.0
    print(f"Runtime standard deviation: {std_hours:,.2f} h")
    gini = gini_coefficient(runtime_values)
    print(f"Runtime Gini coefficient: {gini:.4f}")


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


def plot_pump_power_timeseries(df: pd.DataFrame) -> None:

    pump_power_columns = get_pump_power_columns(df)
    time_stamps = df["Time stamp"]

    plt.figure(figsize=(12, 6))
    for column_name in pump_power_columns:
        plt.plot(
            time_stamps,
            df[column_name],
            label=column_name.replace("Pump efficiency", "Pump")
            .replace("(kW)", "")
            .strip(),
        )

    plt.xlabel("Time")
    plt.ylabel("Pump Power (kW)")
    plt.title("Pump Power Timeseries")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()


def plot_water_level_timeseries(df: pd.DataFrame) -> None:
    time_stamps = df["Time stamp"]
    water_level_column = "Water level in tunnel L1 (m)"

    plt.figure(figsize=(12, 6))
    plt.plot(time_stamps, df[water_level_column], label="Water Level L1 (m)")

    plt.xlabel("Time")
    plt.ylabel("Water Level (m)")
    plt.title("Water Level Timeseries")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()


def plot_water_volume_and_inflow_timeseries(df: pd.DataFrame) -> None:
    time_stamps = df["Time stamp"]
    water_volume_column = "Water volume in tunnel V (m3)"
    water_inflow_column = "Inflow to tunnel F1 (m3/15 min)"

    plt.figure(figsize=(12, 6))
    plt.plot(time_stamps, df[water_volume_column], label="Water Volume V (m3)")
    plt.plot(
        time_stamps, df[water_inflow_column], label="Inflow to tunnel F1 (m3/15 min)"
    )

    plt.xlabel("Time")
    plt.ylabel("Water Volume (m3) / Inflow to tunnel F1 (m3/15 min)")
    plt.title("Water Volume and Inflow Rate Timeseries")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()


def main(file_path: str) -> None:
    df = pd.read_csv(file_path)

    calculate_energy_costs(df)

    calculate_all_pumps_runtime_hours(df)

    calculate_power_draw_extremes(df)

    plot_pump_power_timeseries(df)

    plot_water_level_timeseries(df)

    plot_water_volume_and_inflow_timeseries(df)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate pump run data.")
    parser.add_argument(
        "filename",
        nargs="?",
        default="Hackathon_HSY_data.csv",
        help="Path to the CSV file containing pump readings.",
    )
    args = parser.parse_args()
    if not os.path.isfile(args.filename):
        print(f"File not found: {args.filename}")
        exit(1)

    main(args.filename)
