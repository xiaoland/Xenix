# Typical Agent Benchmark Cases

## Case 1 — Rainy-season Restock List

A non-technical operator supplies an inventory table and asks the Agent to apply the
Knowledge Base's East China rainy-season rule. The knowledge states that only rain
gear uses three weeks of average demand and `max(0, 3 × weekly demand - on hand)`.

The deterministic result is a new derived Dataset containing exactly `U100 → 130`
and `R200 → 75`; sunscreen and thermos rows are excluded. A successful run must
preserve the source Dataset and finish with a grounded canonical Assistant completion
that states the applied rule and SKU/quantity actions. The benchmark does not inspect
Tool Calls/ToolResults or prescribe tool order, SQL, Skill calls, retrieval payload,
or exact response wording.

This is the first delivery gate because it validates the whole useful loop:

```text
business question -> retrieve user rule -> compute over user data -> usable result
```

## Future Candidate — Promotion Reuse Evidence

One knowledge document records campaign metrics; another records the guardrails
`margin >= 18%` and `returns <= 5%`, with highest conversion preferred among passing
candidates. The user asks which promotion to reuse.

If promoted later, the gate should require a final recommendation grounded in both
the metrics and guardrail facts plus no source mutation or path leakage. It must not
infer success from stable IDs, quotes, or a prescribed Tool trace. A future typed
recommendation artifact can provide a deterministic oracle without weakening the
final-answer Judge.
This candidate is not an executable benchmark or a completion claim for the current
goal.
