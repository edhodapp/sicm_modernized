"""First test stub — deliberately-failing canary for the test pipeline.

Per pyproject.toml's "deliberately-failing hello-world" pattern (which
matches iomoments at the same project phase), this test asserts a
contradiction so it always FAILS. The `xfail(strict=True)` marker
flips the result to XFAIL so the suite still reports green — but if
the test ever passes (e.g., someone removes the assertion or flips
its sense without removing the marker), strict=True turns the XPASS
into an outright suite failure.

Properties this canary proves end-to-end:
  - pytest discovers tests under repo-root `tests/`
  - pytest's xfail mechanism is wired (strict=True path)
  - the pre-commit hook chain invokes pytest and treats the suite
    result correctly (XFAIL passing through, XPASS failing)

The canary is intended to remain in place as a perpetual pipeline
self-check — its falsified assertion is the feature, not a bug. To
RETIRE the canary once enough real tests cover the pipeline-wiring
properties above, DELETE THE WHOLE FILE; do NOT flip the assertion
or relax the marker, since either of those silently destroys the
self-check property.
"""

import pytest


@pytest.mark.xfail(
    strict=True,
    reason=(
        "deliberately-failing pipeline canary; XPASS would mean the "
        "assertion was changed without removing the xfail marker, "
        "indicating a misconfigured test rather than real work — "
        "to retire this canary, delete the whole file rather than "
        "flipping the assertion"
    ),
)
def test_pipeline_canary_deliberately_fails() -> None:
    """Falsified assertion. See module docstring for rationale."""
    assert False, "deliberately failing first test stub"
