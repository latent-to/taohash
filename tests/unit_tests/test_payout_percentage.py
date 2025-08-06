"""Test the calculate_payout_percentage function."""

from unittest.mock import Mock

import pytest

from taohash.core.constants import (
    CEILING_PERCENTAGE,
    CEILING_PH,
    FLOOR_PERCENTAGE,
    FLOOR_PH,
)
from taohash.validator.validator import TaohashProxyValidator


class TestPayoutPercentage:
    """Test suite for the payout percentage calculation."""

    @pytest.fixture
    def validator(self):
        """Create a validator instance with mocked dependencies."""
        validator = Mock(spec=TaohashProxyValidator)
        validator.price_api = Mock()
        validator.hash_price_api = Mock()

        # Set up the method we're testing
        validator.calculate_payout_percentage = (
            TaohashProxyValidator.calculate_payout_percentage.__get__(validator)
        )

        # Mock API responses
        validator.price_api.get_price.return_value = 100000  # $100k BTC
        validator.hash_price_api.get_hash_value.return_value = 5e-07  # BTC/TH/day

        return validator

    @pytest.mark.parametrize(
        "hashpower_ph,expected_percentage",
        [
            (1, FLOOR_PERCENTAGE),  # Very small miner
            (10, FLOOR_PERCENTAGE),  # Small miner
            (20, FLOOR_PERCENTAGE),  # Below threshold
            (30, FLOOR_PERCENTAGE),  # At minimum threshold
            (1000, CEILING_PERCENTAGE),  # At max threshold
            (1500, CEILING_PERCENTAGE),  # Above threshold
            (5000, CEILING_PERCENTAGE),  # Very large miner
        ],
    )
    def test_boundary_cases(self, validator, hashpower_ph, expected_percentage):
        """Test that boundary cases return correct percentages."""
        time_seconds = 3600  # 1 hour
        btc_price = 100000
        hash_value_btc = 5e-07

        # Calculate share value for this hashpower
        btc_per_ph_per_second = (hash_value_btc * 1000) / 86400
        btc_earned = hashpower_ph * btc_per_ph_per_second * time_seconds
        share_value = btc_earned * btc_price

        percentage = validator.calculate_payout_percentage(
            share_value, time_seconds, hash_value_btc, btc_price
        )

        assert abs(percentage - expected_percentage) < 0.01

    @pytest.mark.parametrize("hashpower_ph", [50, 100, 300, 500, 700, 900])
    def test_middle_range_values(self, validator, hashpower_ph):
        """Test that middle range values are within valid bounds."""
        time_seconds = 3600
        btc_price = 100000
        hash_value_btc = 5e-07

        btc_per_ph_per_second = (hash_value_btc * 1000) / 86400
        btc_earned = hashpower_ph * btc_per_ph_per_second * time_seconds
        share_value = btc_earned * btc_price

        percentage = validator.calculate_payout_percentage(
            share_value, time_seconds, hash_value_btc, btc_price
        )

        assert FLOOR_PERCENTAGE <= percentage <= CEILING_PERCENTAGE

        # Additional check: larger hashpower should have higher percentage
        if hashpower_ph > FLOOR_PH:
            assert percentage > FLOOR_PERCENTAGE
        if hashpower_ph < CEILING_PH:
            assert percentage < CEILING_PERCENTAGE

    def test_s_curve_smoothness(self, validator):
        """Test that the S-curve progression is smooth without jumps."""
        time_seconds = 3600
        btc_price = 100000
        hash_value_btc = 5e-07
        btc_per_ph_per_second = (hash_value_btc * 1000) / 86400

        test_points = [30, 50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
        percentages = []

        for hashpower_ph in test_points:
            btc_earned = hashpower_ph * btc_per_ph_per_second * time_seconds
            share_value = btc_earned * btc_price
            percentage = validator.calculate_payout_percentage(
                share_value, time_seconds, hash_value_btc, btc_price
            )
            percentages.append(percentage)

        # Check monotonic increase
        for i in range(1, len(percentages)):
            assert percentages[i] >= percentages[i - 1], (
                "Percentage should not decrease"
            )

            # Check no smooth progression
            change = percentages[i] - percentages[i - 1]
            assert change < 1.0, (
                f"Jump too large between {test_points[i - 1]} and {test_points[i]} PH"
            )

    @pytest.mark.parametrize("time_seconds", [300, 1800, 3600, 21600, 86400])
    def test_time_consistency(self, validator, time_seconds):
        """Test that percentage is consistent for same hashpower at different times."""
        hashpower_ph = 100
        btc_price = 100000
        hash_value_btc = 5e-07

        btc_per_ph_per_second = (hash_value_btc * 1000) / 86400
        btc_earned = hashpower_ph * btc_per_ph_per_second * time_seconds
        share_value = btc_earned * btc_price

        percentage = validator.calculate_payout_percentage(
            share_value, time_seconds, hash_value_btc, btc_price
        )

        # For the same hashpower, percentage should be the same regardless of time period
        # (within small tolerance for floating point)
        expected = 0.537  # Approximate expected value for 100 PH
        assert abs(percentage - expected) < 0.01

    def test_edge_case_zero_share_value(self, validator):
        """Test handling of zero share value."""
        percentage = validator.calculate_payout_percentage(0, 3600, 5e-07, 100000)
        assert percentage == FLOOR_PERCENTAGE

    def test_s_curve_midpoint(self, validator):
        """Test that S-curve midpoint is approximately at the middle."""
        time_seconds = 3600
        btc_price = 100000
        hash_value_btc = 5e-07

        midpoint_ph = (FLOOR_PH + CEILING_PH) / 2

        btc_per_ph_per_second = (hash_value_btc * 1000) / 86400
        btc_earned = midpoint_ph * btc_per_ph_per_second * time_seconds
        share_value = btc_earned * btc_price

        percentage = validator.calculate_payout_percentage(
            share_value, time_seconds, hash_value_btc, btc_price
        )

        expected_midpoint = (FLOOR_PERCENTAGE + CEILING_PERCENTAGE) / 2

        # Should be close to midpoint (within 10% tolerance due to S-curve)
        assert abs(percentage - expected_midpoint) < 0.2
