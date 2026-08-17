"""Keep the paid Agent Harness end-to-end tree out of the offline portfolio.

``pdm run test`` must not collect the live benchmark cases or their
provider-free infrastructure checks.  The benchmark runner and
``pdm run benchmark-agent-harness-check`` re-enable collection by naming the
subtree explicitly on the command line.
"""

from __future__ import annotations

collect_ignore = ["agent_harness"]
