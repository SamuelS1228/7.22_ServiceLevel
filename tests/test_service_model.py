from __future__ import annotations

import pytest

from slo.service_model import adjusted_stock_units, expected_poisson_shortage, poisson_fill_rate


def test_zero_demand_has_no_shortage_and_full_fill() -> None:
    assert expected_poisson_shortage(0.0, 0) == 0.0
    assert poisson_fill_rate(0.0, 0) == 1.0


def test_more_stock_improves_fill_rate() -> None:
    low_stock_fill = poisson_fill_rate(mean_demand=3.0, stock_units=2)
    high_stock_fill = poisson_fill_rate(mean_demand=3.0, stock_units=5)
    assert 0.0 <= low_stock_fill <= 1.0
    assert 0.0 <= high_stock_fill <= 1.0
    assert high_stock_fill > low_stock_fill


def test_expected_shortage_matches_direct_sum() -> None:
    # Independent finite-tail calculation for a stable regression check.
    from scipy.stats import poisson

    mean = 2.7
    stock = 3
    direct = sum((demand - stock) * poisson.pmf(demand, mean) for demand in range(stock + 1, 40))
    assert expected_poisson_shortage(mean, stock) == pytest.approx(direct, abs=1e-10)


def test_adjusted_stock_rounds_up() -> None:
    assert adjusted_stock_units(3, 0.15) == 4
    assert adjusted_stock_units(0, 0.50) == 0
