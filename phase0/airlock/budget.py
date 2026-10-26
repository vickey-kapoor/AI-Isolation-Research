"""The airlock budget: how many artefacts may leave per period.

There is deliberately no method to raise the limit or reopen the airlock.
"Can only close, never widen" (PRD R-L4, R-L7) is enforced by the code not
having the operation, not by a check that someone could switch off.
"""


class BudgetError(ValueError):
    pass


class Budget:
    def __init__(self, max_per_period: int, period_ticks: int):
        if max_per_period < 0 or period_ticks < 1:
            raise BudgetError("invalid budget")
        self._max = max_per_period
        self._period = period_ticks
        self._used = 0
        self._period_start = 0
        self._closed = False

    @property
    def max_per_period(self) -> int:
        return self._max

    @property
    def closed(self) -> bool:
        return self._closed

    def lower(self, new_max: int) -> None:
        if new_max >= self._max or new_max < 0:
            raise BudgetError("the budget can only be lowered")
        self._max = new_max

    def close(self) -> None:
        """Permanent. There is no open()."""
        self._closed = True
        self._max = 0

    def try_spend(self, tick: int) -> bool:
        if tick - self._period_start >= self._period:
            self._period_start = tick - (tick - self._period_start) % self._period
            self._used = 0
        if self._closed or self._used >= self._max:
            return False
        self._used += 1
        return True
