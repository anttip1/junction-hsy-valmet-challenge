from datetime import datetime, timedelta
from app.pump import Pump, PumpType, toggle_pump


class TestPump:
    def test_pump_on_cumulative_time_is_calculated_correct(self) -> None:
        pump = Pump(
            id=1,
            pump_type=PumpType.LARGE,
            current_run_time_start=None,
            activation_times=[],
        )

        assert not pump.is_active
        pump_on_1 = toggle_pump(
            pump,
            (datetime.now() - timedelta(minutes=5)),
        )

        assert pump_on_1.is_active
        pump_off_2 = toggle_pump(pump_on_1, datetime.now())
        assert pump_off_2.cumulative_time_minutes == 5

        pump_on_3 = toggle_pump(
            pump_off_2,
            (datetime.now() - timedelta(minutes=105)),
        )
        pump_off_4 = toggle_pump(pump_on_3, datetime.now())

        assert pump_off_4.cumulative_time_minutes == 110
        assert len(pump_off_4.activation_times) == 2
