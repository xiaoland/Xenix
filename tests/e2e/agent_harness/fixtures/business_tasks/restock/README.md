# Restock decision family

The business goal is to maximize planned incremental margin under a budget, warehouse capacity, arrival deadline and supplier batch limits. Every accepted plan must meet the stated objective; multiple equally optimal purchase combinations are legitimate. A zero optimum permits an explicit, grounded no-purchase answer without generating an empty file.

The standard catalog contains 12 offers for a store event, with whole-batch quantities, distinct supplier limits and late arrivals. Confirmation uses an independently authored 10-offer cosmetics catalog, decimal prices, a different resource balance, an unavailable high-margin offer and a negative-margin offer. These are planning assumptions supplied by the business, not guaranteed future sales or hidden forecasts. `authoring.py` reproduces the static inputs and computes author-only optimum values using a bounded dynamic program. The runner never imports it or supplies `oracle.json` to Subject.

| Scenario | Business change from standard | Expected effect |
| --- | --- | --- |
| `standard` | Reference business input | Two optimal plans, each with planned margin 1,845 yuan. No preferred identity among ties. |
| `budget_tight` | Only budget falls from 3,000 to 2,250 yuan | The selected plan changes; optimum is 1,415 yuan. |
| `arrival_earlier` | Only Q612's promised arrival moves inside the same deadline | The plan changes; optimum rises to 2,050 yuan. |
| `margin_lower` | Only Q203's per-batch planned margin falls from 360 to 220 yuan | The plan changes; three equally optimal plans achieve 1,690 yuan. |
| `margin_higher` | Only Q203's per-batch planned margin rises from 360 to 380 yuan | Both original optimal quantity plans remain optimal; their value rises to 1,885 yuan. |
| `no_purchase` | Only budget falls to 120 yuan | No batch is affordable: no purchase is correct, because the cheapest available batch costs 150 yuan. |
| `confirmation` | Independent catalog, budget, capacity and deadline | Optimum 1,280.65 yuan; not a single-condition diagnostic or an unchanged renamed answer. |

The case accepts a purchased-items table or a full audit table with explicit zero/unselected quantities. Headers and order are flexible. Program projections compute cost, capacity, planned margin and constraint violations for candidate quantity columns; Judge confirms the column and table actually recommended, any totals or unknown rows, and the business explanation. A stock-availability column cannot substitute for purchase quantities. An empty recommendation under an affordable profitable scenario still fails.

Default discovery selects the representative `test_business_restock_decision` node. `--business-variant confirmation` changes that representative input. Explicitly selecting `test_restock_contrast[budget_tight]`, another parameter, or its file selects the named contrasts; the flag does not silently turn a standard contrast into a confirmation contrast. Scenarios are instances of one business family and do not each gain an independent coverage vote. Different-scenario results explain task sensitivity; they are not comparable model-improvement repetitions.

Independent exhaustive enumeration and outcome probes are recorded in the task packet. The small catalog establishes observable tradeoffs, not production demand representativeness. Once confirmation has informed targeted changes, use fresh business material for independent confirmation.
