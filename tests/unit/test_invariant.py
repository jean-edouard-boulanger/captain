import pytest

from captain.core.invariant import invariant, InvariantViolationError


def test_broken_invariant():
    with pytest.raises(InvariantViolationError):
        invariant(False)


def test_invariant():
    invariant(True)
