"""Shenzhen residential monthly tiered electricity tariff calculations."""

from __future__ import annotations

import datetime
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

SUMMER_MONTHS = frozenset(range(5, 11))

# Shenzhen's published all-in price has more precision than the four-decimal
# display table. Keep full precision for calculations and round only values
# exposed to Home Assistant.
# Sources:
# https://fgw.sz.gov.cn/attachment/1/1460/1460239/11394935.pdf
# https://szjgdj.sz.gov.cn/home/ztzl/mxq/jmlb/content/post_1108363.html
FIRST_TIER_PRICE = Decimal("0.66286875")
SECOND_TIER_PRICE = FIRST_TIER_PRICE + Decimal("0.05")
THIRD_TIER_PRICE = FIRST_TIER_PRICE + Decimal("0.30")

SUMMER_FIRST_TIER_LIMIT = Decimal("260")
SUMMER_SECOND_TIER_LIMIT = Decimal("600")
NON_SUMMER_FIRST_TIER_LIMIT = Decimal("200")
NON_SUMMER_SECOND_TIER_LIMIT = Decimal("400")

MONEY_QUANTUM = Decimal("0.01")
TARIFF_DISPLAY_QUANTUM = Decimal("0.0001")

DAILY_CHARGE_SOURCE_API = "csg_api"
DAILY_CHARGE_SOURCE_ESTIMATE = "shenzhen_progressive_tariff_estimate"
SHENZHEN_TARIFF_SOURCE = "shenzhen_residential_2026_standard"


@dataclass(frozen=True)
class ShenzhenTariffCalculation:
    """Calculated tariff state for one Shenzhen residential billing month."""

    tier_code: int
    remaining_kwh: float
    current_tariff: float
    estimated_cost: float
    season: str
    first_tier_limit_kwh: float
    second_tier_limit_kwh: float


def _validate_month(month: int) -> None:
    if month not in range(1, 13):
        raise ValueError(f"month must be in 1..12, got {month}")


def _usage_decimal(consumption_kwh: int | float | str | Decimal) -> Decimal:
    usage = Decimal(str(consumption_kwh))
    if not usage.is_finite() or usage < 0:
        raise ValueError(
            f"consumption_kwh must be a finite non-negative number, got {usage}"
        )
    return usage


def _tariff_limits(month: int) -> tuple[Decimal, Decimal, str]:
    _validate_month(month)
    if month in SUMMER_MONTHS:
        return SUMMER_FIRST_TIER_LIMIT, SUMMER_SECOND_TIER_LIMIT, "summer"
    return NON_SUMMER_FIRST_TIER_LIMIT, NON_SUMMER_SECOND_TIER_LIMIT, "non_summer"


def _progressive_cost(
    usage: Decimal, first_limit: Decimal, second_limit: Decimal
) -> Decimal:
    if usage <= first_limit:
        return usage * FIRST_TIER_PRICE
    if usage <= second_limit:
        return (
            first_limit * FIRST_TIER_PRICE
            + (usage - first_limit) * SECOND_TIER_PRICE
        )
    return (
        first_limit * FIRST_TIER_PRICE
        + (second_limit - first_limit) * SECOND_TIER_PRICE
        + (usage - second_limit) * THIRD_TIER_PRICE
    )


def calculate_shenzhen_residential_tariff(
    month: int, consumption_kwh: int | float | str | Decimal
) -> ShenzhenTariffCalculation:
    """Calculate a progressive monthly tariff from cumulative monthly usage.

    Tier codes 2, 3 and 4 match the integration's existing values for
    residential tiers one, two and three.
    """
    usage = _usage_decimal(consumption_kwh)
    first_limit, second_limit, season = _tariff_limits(month)

    if usage <= first_limit:
        tier_code = 2
        remaining = first_limit - usage
        current_tariff = FIRST_TIER_PRICE
    elif usage <= second_limit:
        tier_code = 3
        remaining = second_limit - usage
        current_tariff = SECOND_TIER_PRICE
    else:
        tier_code = 4
        remaining = Decimal("0")
        current_tariff = THIRD_TIER_PRICE

    estimated_cost = _progressive_cost(usage, first_limit, second_limit)

    return ShenzhenTariffCalculation(
        tier_code=tier_code,
        remaining_kwh=float(remaining),
        current_tariff=float(
            current_tariff.quantize(
                TARIFF_DISPLAY_QUANTUM,
                rounding=ROUND_HALF_UP,
            )
        ),
        estimated_cost=float(
            estimated_cost.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
        ),
        season=season,
        first_tier_limit_kwh=float(first_limit),
        second_tier_limit_kwh=float(second_limit),
    )


def calculate_shenzhen_daily_costs(
    year_month: tuple[int, int],
    daily_usage: Sequence[Mapping[str, Any]],
    *,
    preserve_existing_charges: bool = True,
) -> list[dict[str, Any]]:
    """Fill missing daily charges from cumulative progressive monthly cost.

    Each estimate is the difference between two rounded cumulative month
    totals. A day crossing a tier threshold is therefore split correctly, and
    estimated daily charges add up to the rounded monthly estimate. Any charge
    supplied by CSG remains untouched and is marked as an API value.
    """
    year, month = year_month
    _validate_month(month)
    if year < 1:
        raise ValueError(f"year must be positive, got {year}")

    first_limit, second_limit, _ = _tariff_limits(month)
    cumulative_usage = Decimal("0")
    previous_rounded_cost = Decimal("0")
    seen_dates: set[str] = set()
    enriched: list[dict[str, Any]] = []

    for source_record in sorted(
        daily_usage, key=lambda item: str(item.get("date", ""))
    ):
        record = dict(source_record)
        date_value = str(record.get("date", ""))
        try:
            parsed_date = datetime.date.fromisoformat(date_value)
        except ValueError as exc:
            raise ValueError(f"invalid daily usage date: {date_value!r}") from exc
        if (parsed_date.year, parsed_date.month) != year_month:
            raise ValueError(
                f"daily usage date {date_value} is outside {year:04d}-{month:02d}"
            )
        if date_value in seen_dates:
            raise ValueError(f"duplicate daily usage date: {date_value}")
        seen_dates.add(date_value)

        day_usage = _usage_decimal(record.get("kwh"))
        cumulative_usage += day_usage
        rounded_cumulative_cost = _progressive_cost(
            cumulative_usage, first_limit, second_limit
        ).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
        estimated_daily_charge = rounded_cumulative_cost - previous_rounded_cost
        previous_rounded_cost = rounded_cumulative_cost

        tariff_state = calculate_shenzhen_residential_tariff(month, cumulative_usage)
        existing_charge = record.get("charge")
        use_existing_charge = preserve_existing_charges and not (
            existing_charge is None
            or (
                isinstance(existing_charge, str)
                and existing_charge in {"unavailable", "unknown", "unchanged"}
            )
        )

        if use_existing_charge:
            charge = Decimal(str(existing_charge))
            if not charge.is_finite() or charge < 0:
                raise ValueError(
                    f"daily charge must be a finite non-negative number, got {charge}"
                )
            record["charge"] = float(charge)
            record["cost_source"] = record.get(
                "cost_source", DAILY_CHARGE_SOURCE_API
            )
            record["cost_estimated"] = bool(record.get("cost_estimated", False))
        else:
            record["charge"] = float(estimated_daily_charge)
            record["cost_source"] = DAILY_CHARGE_SOURCE_ESTIMATE
            record["cost_estimated"] = True

        record["kwh"] = float(day_usage)
        record["cumulative_kwh"] = float(cumulative_usage)
        record["tier_code"] = tariff_state.tier_code
        record["tariff"] = tariff_state.current_tariff
        enriched.append(record)

    return enriched
