# Typical Agent Benchmark Cases

## Case 1 — Rainy-season Restock List

A non-technical operator supplies an inventory table and asks the Agent to apply the
Knowledge Base's East China rainy-season rule. The knowledge states that only rain
gear uses three weeks of average demand and `max(0, 3 × weekly demand - on hand)`.

The deterministic result is a new derived Dataset containing exactly `U100 → 130`
and `R200 → 75`; sunscreen and thermos rows are excluded. A successful run must also
contain a bounded citation to the rule unit, preserve the source Dataset, and finish
with a canonical Assistant completion. The benchmark does not prescribe tool order,
SQL, Skill calls, or response wording.

This is the first delivery gate because it validates the whole useful loop:

```text
business question -> retrieve user rule -> compute over user data -> usable result
```

## Future Candidate — Promotion Reuse Evidence

One knowledge document records campaign metrics; another records the guardrails
`margin >= 18%` and `returns <= 5%`, with highest conversion preferred among passing
candidates. The user asks which promotion to reuse.

If promoted later, the gate should require evidence from both the metrics unit and guardrail unit, bounded
quotes with stable citations, and no source mutation or path leakage. Under the current
benchmark policy this proves the Agent acquired sufficient evidence, not that its
free-form final sentence selected the right campaign. A future typed recommendation
artifact can close that remaining answer-quality gap without weakening the Judge.
This candidate is not an executable benchmark or a completion claim for the current
goal.
