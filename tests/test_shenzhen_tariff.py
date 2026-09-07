"""Boundary tests for the optional Shenzhen residential tariff estimator."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

INTEGRATION_ROOT = (
    Path(__file__).parents[1]
    / "custom_components"
    / "china_southern_power_grid_stat"
)
sys.path.insert(0, str(INTEGRATION_ROOT))

from shenzhen_tariff import (  # noqa: E402
    DAILY_CHARGE_SOURCE_API,
    DAILY_CHARGE_SOURCE_ESTIMATE,
    SHENZHEN_TARIFF_SOURCE,
    calculate_shenzhen_daily_costs,
    calculate_shenzhen_residential_tariff,
)


@pytest.mark.parametrize("month", [5, 6, 7, 8, 9, 10])
def test_summer_thresholds_and_prices(month):
    first = calculate_shenzhen_residential_tariff(month, 260)
    second = calculate_shenzhen_residential_tariff(month, 260.01)
    third = calculate_shenzhen_residential_tariff(month, 600.01)

    assert (first.tier_code, first.remaining_kwh, first.current_tariff) == (
        2,
        0,
        0.6629,
    )
    assert (second.tier_code, second.remaining_kwh, second.current_tariff) == (
        3,
        339.99,
        0.7129,
    )
    assert (third.tier_code, third.remaining_kwh, third.current_tariff) == (
        4,
        0,
        0.9629,
    )
    assert first.season == "summer"


@pytest.mark.parametrize("month", [1, 2, 3, 4, 11, 12])
def test_non_summer_thresholds_and_prices(month):
    first = calculate_shenzhen_residential_tariff(month, 200)
    second = calculate_shenzhen_residential_tariff(month, 200.01)
    third = calculate_shenzhen_residential_tariff(month, 400.01)

    assert (first.tier_code, first.remaining_kwh, first.current_tariff) == (
        2,
        0,
        0.6629,
    )
    assert (second.tier_code, second.remaining_kwh, second.current_tariff) == (
        3,
        199.99,
        0.7129,
    )
    assert (third.tier_code, third.remaining_kwh, third.current_tariff) == (
        4,
        0,
        0.9629,
    )
    assert first.season == "non_summer"


def test_full_precision_is_used_before_rounding_money():
    result = calculate_shenzhen_residential_tariff(8, 367.88)

    assert result.estimated_cost == 249.25
    assert result.current_tariff == 0.7129
    assert SHENZHEN_TARIFF_SOURCE == "shenzhen_residential_2026_standard"


def test_a_new_month_resets_cumulative_tier_state():
    august = calculate_shenzhen_residential_tariff(8, 610)
    september = calculate_shenzhen_residential_tariff(9, 16.4)

    assert august.tier_code == 4
    assert september.tier_code == 2
    assert september.remaining_kwh == 243.6


def test_daily_cost_splits_a_day_that_crosses_a_tier():
    by_day = calculate_shenzhen_daily_costs(
        (2026, 8),
        [
            {"date": "2026-08-01", "kwh": 250},
            {"date": "2026-08-02", "kwh": 20},
        ],
    )

    assert by_day[0]["charge"] == 165.72
    assert by_day[0]["tier_code"] == 2
    assert by_day[1]["charge"] == 13.75
    assert by_day[1]["tier_code"] == 3
    assert by_day[1]["tariff"] == 0.7129
    assert sum(day["charge"] for day in by_day) == pytest.approx(
        calculate_shenzhen_residential_tariff(8, 270).estimated_cost
    )


def test_daily_costs_sort_dates_and_preserve_api_charges():
    by_day = calculate_shenzhen_daily_costs(
        (2026, 11),
        [
            {"date": "2026-11-02", "kwh": 10},
            {"date": "2026-11-01", "kwh": 10, "charge": 6.7},
        ],
    )

    assert [day["date"] for day in by_day] == ["2026-11-01", "2026-11-02"]
    assert by_day[0]["charge"] == 6.7
    assert by_day[0]["cost_source"] == DAILY_CHARGE_SOURCE_API
    assert by_day[0]["cost_estimated"] is False
    assert by_day[1]["charge"] == 6.63
    assert by_day[1]["cost_source"] == DAILY_CHARGE_SOURCE_ESTIMATE
    assert by_day[1]["cost_estimated"] is True


def test_daily_estimates_sum_to_rounded_month_total():
    by_day = calculate_shenzhen_daily_costs(
        (2026, 8),
        [
            {"date": "2026-08-01", "kwh": 250},
            {"date": "2026-08-02", "kwh": 340},
            {"date": "2026-08-03", "kwh": 20},
        ],
    )

    assert sum(day["charge"] for day in by_day) == pytest.approx(
        calculate_shenzhen_residential_tariff(8, 610).estimated_cost
    )
    assert by_day[-1]["tier_code"] == 4


def test_unavailable_charge_is_replaced_but_zero_is_preserved():
    by_day = calculate_shenzhen_daily_costs(
        (2026, 9),
        [
            {"date": "2026-09-01", "kwh": 0, "charge": 0},
            {"date": "2026-09-02", "kwh": 1, "charge": "unavailable"},
        ],
    )

    assert by_day[0]["charge"] == 0
    assert by_day[0]["cost_estimated"] is False
    assert by_day[1]["charge"] == 0.66
    assert by_day[1]["cost_estimated"] is True


@pytest.mark.parametrize(
    ("month", "usage"),
    [(0, 10), (13, 10), (7, -0.01), (7, "NaN")],
)
def test_invalid_month_or_usage_is_rejected(month, usage):
    with pytest.raises(ValueError):
        calculate_shenzhen_residential_tariff(month, usage)


def test_cross_month_and_duplicate_daily_rows_are_rejected():
    with pytest.raises(ValueError, match="outside"):
        calculate_shenzhen_daily_costs(
            (2026, 9), [{"date": "2026-08-31", "kwh": 1}]
        )
    with pytest.raises(ValueError, match="duplicate"):
        calculate_shenzhen_daily_costs(
            (2026, 9),
            [
                {"date": "2026-09-01", "kwh": 1},
                {"date": "2026-09-01", "kwh": 2},
            ],
        )
