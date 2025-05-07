import pytest

from taohash.core.pool.metrics import MiningMetrics

class TestAddingMetrics:

    @pytest.mark.parametrize("hr5m0,hr60m0,"
                             "hr5m1,hr60m1,"
                             "shares5m0,shares60m0,"
                             "shares5m1,shares60m1,", [
        (14, 24, 33, 44, 55, 66, 77, 88),
        (112.343, 1291.343, 112.343, 12.456, 112.343, 901.2, 90.343, 333.343),
    ])
    def test_adding_metrics_same_unit(self, hr5m0, hr60m0, hr5m1, hr60m1, shares5m0, shares60m0, shares5m1, shares60m1):
        metrics1 = MiningMetrics(hotkey="1234567890", hash_rate_5m=hr5m0, hash_rate_60m=hr60m0, hash_rate_unit="Th/s", shares_5m=shares5m0, shares_60m=shares60m0)
        metrics2 = MiningMetrics(hotkey="1234567890", hash_rate_5m=hr5m1, hash_rate_60m=hr60m1, hash_rate_unit="Th/s", shares_5m=shares5m1, shares_60m=shares60m1)
        metrics3 = metrics1 + metrics2

        # These should all sum; same unit
        assert metrics3.hash_rate_5m == hr5m0 + hr5m1
        assert metrics3.hash_rate_60m == hr60m0 + hr60m1
        assert metrics3.shares_5m == shares5m0 + shares5m1
        assert metrics3.shares_60m == shares60m0 + shares60m1

        assert metrics3.hash_rate_unit == "Th/s"
    
    @pytest.mark.parametrize("hr5m0,hr60m0,"
                             "hr5m1,hr60m1,"
                             "shares5m0,shares60m0,"
                             "shares5m1,shares60m1,", [
        (14, 24, 33, 44, 55, 66, 77, 88),
        (112.343, 1291.343, 112.343, 12.456, 112.343, 901.2, 90.343, 333.343),
    ])
    def test_adding_metrics_different_unit(self, hr5m0, hr60m0, hr5m1, hr60m1, shares5m0, shares60m0, shares5m1, shares60m1):
        metrics1 = MiningMetrics(hotkey="1234567890", hash_rate_5m=hr5m0, hash_rate_60m=hr60m0, hash_rate_unit="Th/s", shares_5m=shares5m0, shares_60m=shares60m0)
        metrics2 = MiningMetrics(hotkey="1234567890", hash_rate_5m=hr5m1, hash_rate_60m=hr60m1, hash_rate_unit="Gh/s", shares_5m=shares5m1, shares_60m=shares60m1)
        metrics3 = metrics1 + metrics2

        # These should all sum; same unit
        assert metrics3.hash_rate_5m == hr5m0 + hr5m1 / 1000
        assert metrics3.hash_rate_60m == hr60m0 + hr60m1 / 1000
        assert metrics3.shares_5m == shares5m0 + shares5m1 # shares are not affected by unit
        assert metrics3.shares_60m == shares60m0 + shares60m1 # shares are not affected by unit

        assert metrics3.hash_rate_unit == "Th/s" # should use Th/s as the unit
