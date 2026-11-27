# Active Task Packets

Volatile working packets for in-progress tasks live under `tasks/`. Durable product, architecture, and deployment knowledge belongs in [docs](../docs/index.md), which must never depend on or link into `tasks/`.

Finished task packets are pruned once their durable conclusions are promoted to `docs/`, source, and tests; historical packets from v1.2–v1.6 remain preserved in Git history.
