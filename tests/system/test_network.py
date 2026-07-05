"""Unit tests for the pure helper functions in `app.system.metrics.network`.

Both functions are plain synchronous transforms over already-collected ping
results / interface speeds, so they need no mocking, no event loop, and no
real network access -- ideal first candidates for a test suite.
"""

from app.system.metrics.network import _format_link_speed, _summarize_pings
from app.system.metrics.utils import UNKNOWN_VALUE


class TestSummarizePings:
    def test_all_hosts_alive_reports_full_success_and_latency(self):
        success, latency = _summarize_pings([10.0, 20.0, 30.0])

        assert success == '3/3'
        assert 'avg[20.0ms]' in latency
        assert 'max[30.0ms]' in latency

    def test_all_hosts_down_reports_zero_success_and_unknown_latency(self):
        success, latency = _summarize_pings([None, None])

        assert success == '0/2'
        assert latency == UNKNOWN_VALUE

    def test_partial_availability_only_counts_alive_hosts_for_latency(self):
        success, latency = _summarize_pings([10.0, None, 30.0])

        assert success == '2/3'
        assert 'avg[20.0ms]' in latency
        assert 'max[30.0ms]' in latency

    def test_empty_results_reports_zero_of_zero(self):
        success, latency = _summarize_pings([])

        assert success == '0/0'
        assert latency == UNKNOWN_VALUE


class TestFormatLinkSpeed:
    def test_zero_or_negative_speed_returns_none(self):
        assert _format_link_speed(0) is None
        assert _format_link_speed(-1) is None

    def test_sub_gigabit_speed_formatted_in_megabits(self):
        assert _format_link_speed(100) == '100M'

    def test_exact_gigabit_speed_has_no_decimal(self):
        assert _format_link_speed(1000) == '1G'

    def test_multi_gigabit_whole_number_has_no_decimal(self):
        assert _format_link_speed(10000) == '10G'

    def test_fractional_gigabit_speed_keeps_decimal(self):
        assert _format_link_speed(2500) == '2.5G'
