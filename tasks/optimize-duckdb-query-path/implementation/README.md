# Implementation Plan Index

Implementation plans are execution working sets, not mutation authorization and not run history.

| Plan | Handshake | Status | Purpose |
| --- | --- | --- | --- |
| [Plan-1 — remove pandas round-trip](plan-1-pandas-roundtrip.md) | IH-1 | superseded | (descoped; evidence showed marginal win) |
| [Plan-2 — CSV direct scan](plan-2-csv-direct-scan.md) | IH-2 | superseded | (descoped; dead path + correctness hazards) |
| [Plan-3 — connection reuse](plan-3-connection-reuse.md) | [IH-3](../handshakes/IH-3-connection-reuse.md) | ready after approval | Thread-local connection reuse with temp-object teardown |
| [Plan-4 — dead-code cleanup](plan-4-dead-code-cleanup.md) | [IH-4](../handshakes/IH-4-dead-code-cleanup.md) | ready after approval | Remove CSV fallback + unreachable helpers; smoke → parquet |

Plan-3 and Plan-4 both touch `data_transform.py` and `app.py`; execute them in one working session, Plan-3 first, then Plan-4, then run the shared verification once.
