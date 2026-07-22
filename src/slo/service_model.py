"""Service-level calculations used to evaluate dealer policy candidates."""

from __future__ import annotations

import math

import numpy as np
from scipy.stats import poisson


def expected_poisson_shortage(mean_demand: float, stock_units: int) -> float:
    """Return E[(D - S)+] for Poisson demand ``D`` and stock ``S``.

    The closed form avoids summing the infinite Poisson tail:

    E[(D-S)+] = λ P(D >= S) - S P(D > S)
    """
    if mean_demand <= 0:
        return 0.0
    stock = max(int(stock_units), 0)
    probability_at_least_stock = float(poisson.sf(stock - 1, mean_demand))
    probability_above_stock = float(poisson.sf(stock, mean_demand))
    shortage = mean_demand * probability_at_least_stock - stock * probability_above_stock
    return max(shortage, 0.0)


def poisson_fill_rate(mean_demand: float, stock_units: int) -> float:
    """Estimate unit fill rate during a protection period."""
    if mean_demand <= 0:
        return 1.0
    shortage = expected_poisson_shortage(mean_demand, stock_units)
    return float(np.clip(1.0 - shortage / mean_demand, 0.0, 1.0))


def adjusted_stock_units(base_stock_units: float, inventory_uplift_pct: float) -> int:
    """Apply the candidate inventory uplift and round to whole units."""
    return max(0, int(math.ceil(float(base_stock_units) * (1.0 + float(inventory_uplift_pct)))))
