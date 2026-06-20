# Objective & Hypothesis

Diagnose a customer report: one training run involved 5 target/dependent columns, but the final training used only 4.

Initial hypothesis: the loss happened between the agent/tool argument layer and ML task request payload, or at a model-specific single-target validation/projection boundary.

# Guardrails Touched

- Customer SQLite database and Excel must be read-only.
- Do not launch Xenix against the normal user profile or overwrite local User-level Xenix state.
- Treat this as `Reality / Diagnose`: evidence first, no source-code mutation.

# Verification

- Inspect customer database schema and row counts using read-only SQLite connection.
- Locate dataset records for `股票客户流失.xlsx`.
- Link dataset -> agent conversation/tool calls -> ML task/trained model/artifacts.
- Compare target/dependent column counts across tool arguments, role bindings, ML task payloads, trained model metadata, and source Excel columns.

# Current Understanding

- Storage models show `dataset`, `dataset_column_binding`, `ml_task`, `agent_*`, `artifact`, and `trained_model` tables.
- Agent Harness owns conversation, tool-call, tool-result, provider request, and run records.
- Generalized ML lifecycle persists immutable role bindings; older feature/target column fields are migration inputs only.
- Customer DB was opened read-only via SQLite URI `mode=ro`; no Xenix runtime was launched.
- Customer Excel `股票客户流失.xlsx` has 7043 rows and 6 columns:
  - 5 candidate feature columns: `账户资金（元）`, `最后一次交易距今时间（天）`, `上月交易佣金（元）`, `累计交易佣金（元）`, `本券商使用时长（年）`
  - 1 target column: `是否流失`
- DB dataset chain:
  - source dataset `6ba149dd4a9d406e9ab7ba7c4977356d32` / `股票客户流失`
  - transformed dataset `f053a175190f43f785a3b453f35b1d23` / `股票客户流失_已清理`
  - apply-result dataset `bf2de3fff37242239cd0d47f4ca679ec`
- Conversation evidence:
  - Assistant first said the model could use "5 metrics".
  - It then concluded `账户资金 = 90 * 累计交易佣金 - 160000` and explicitly decided to keep only one of the perfectly linearly related columns.
  - `data.clean` with `drop_columns` failed as unsupported.
  - `data.transform` succeeded with SQL selecting 5 total columns, excluding `累计交易佣金（元）`.
  - `data.feature.select` bound 4 feature columns and 1 target column.
  - `model.train` used binding `d6090a081ff74832817519091ac88b51`.
- Training evidence:
  - Fit tasks `829253accb984843b63ba5c2bd94c2f7` and `ae341a3e38324b49a6f578469057ad7e` both persisted 4 feature columns and target `是否流失`.
  - Trained model metadata for both logistic regression and XGBoost matches the same 4 feature + 1 target contract.
  - There is no evidence in this DB that 5 target columns were persisted and then truncated to 4.
- Code-path evidence:
  - `model.train` passes the stored binding to ML service.
  - ML service validates supervised models require exactly one target; it raises rather than silently truncating target count.
  - Numeric supervised execution uses `target_columns[0]` only after the exact-one-target validation.

# Next Step

If this turns into a product/code change, likely owner is the agent decision/explanation layer: make feature exclusion explicit and confirm with the user before dropping a candidate predictor, or present "5 original predictors -> 4 trained predictors + 1 target" clearly.

# Execution Update

- User approved the prompt-only fix.
- Added one default system prompt sentence requiring the agent to explain field exclusions/merges/non-use and list original candidate fields, actually used fields, and the target field before proceeding.
- Added a focused harness test assertion for the new prompt contract.
- Updated the agent harness unit TDD summary to reflect the new prompt contract.
- Verification: `pdm run pytest tests/test_agent_harness_foundation.py::test_conversation_store_formats_default_system_prompt_with_interface_locale` passed.
