"""Keep the paid Agent Harness end-to-end tree out of the offline portfolio.

``pdm run test`` must not collect the live benchmark cases. The benchmark
runner enables collection by naming the subtree explicitly on the command line.
"""

from __future__ import annotations

collect_ignore = ["agent_harness"]
