"""Packaged runtime smoke checks.

Validates platform integrity when the app starts in ``smoke_test`` mode.
Each check verifies a system capability (DuckDB, Polars, Vega-Lite, Wordcloud,
XGBoost, and each ML service) and raises ``RuntimeError`` on failure.
"""

from __future__ import annotations

from pathlib import Path

from .config import AppPaths


def run_smoke_checks(paths: AppPaths) -> None:
    import pandas as pd
    from polars._cpu_check import get_runtime_repr

    from .services.analysis_graph import AnalysisGraphService, GraphDatasetInput
    from .services.data_transform import (
        DataQueryInput,
        DataQueryTransformService,
        DatasetSqlBinding,
    )
    from .services.dataset_inspection import detect_source_format
    from .services.ml.models.regression import XGBoostRegressionService
    from .services.tabular import load_tabular_frame

    if get_runtime_repr() != "rtcompat":
        raise RuntimeError("Polars packaged runtime smoke expected rtcompat runtime.")

    duckdb_smoke_path = paths.temp / "duckdb-smoke.parquet"
    pd.DataFrame({"value": [1, 2]}).to_parquet(duckdb_smoke_path)
    result = DataQueryTransformService(paths).query(
        DataQueryInput(
            bindings=[
                DatasetSqlBinding(
                    alias="input",
                    dataset_id="smoke-dataset",
                    source_path=str(duckdb_smoke_path.resolve()),
                )
            ],
            sql="SELECT SUM(value) AS total FROM input",
            limit=1,
        )
    )
    if not result.rows or result.rows[0].get("total") != 3:
        raise RuntimeError("DuckDB smoke query failed.")

    tabular_csv_smoke_path = paths.temp / "tabular-smoke.csv"
    tabular_csv_smoke_path.write_text("label,value\nA,1\nB,2\n", encoding="utf-8")
    csv_frame = load_tabular_frame(
        tabular_csv_smoke_path,
        detect_source_format(tabular_csv_smoke_path),
    )
    if csv_frame.height != 2 or csv_frame.width != 2:
        raise RuntimeError("Polars CSV smoke read failed.")

    tabular_xlsx_smoke_path = paths.temp / "tabular-smoke.xlsx"
    pd.DataFrame([{"label": "A", "value": 1}, {"label": "B", "value": 2}]).to_excel(
        tabular_xlsx_smoke_path,
        index=False,
    )
    xlsx_frame = load_tabular_frame(
        tabular_xlsx_smoke_path,
        detect_source_format(tabular_xlsx_smoke_path),
    )
    if xlsx_frame.height != 2 or xlsx_frame.width != 2:
        raise RuntimeError("Polars Excel smoke read failed.")

    graph_smoke_path = paths.temp / "graph-smoke.csv"
    graph_smoke_path.write_text("label,value\nA,1\nB,2\n", encoding="utf-8")
    graph_result = AnalysisGraphService(paths).graph_dataset(
        GraphDatasetInput(
            source_path=str(graph_smoke_path.resolve()),
            dataset_name="Graph smoke",
            spec={
                "width": 300,
                "height": 180,
                "title": "Graph smoke",
                "mark": "bar",
                "encoding": {
                    "x": {"field": "label", "type": "nominal"},
                    "y": {"field": "value", "type": "quantitative"},
                    "color": {"value": "#4c78a8"},
                },
            },
        )
    )
    graph_output = Path(graph_result.output_path)
    if not graph_output.is_file() or not graph_output.read_text(encoding="utf-8").lstrip().startswith("<svg"):
        raise RuntimeError("Vega-Lite graph smoke render failed.")

    wordcloud_smoke_path = paths.temp / "graph-wordcloud-smoke.csv"
    wordcloud_smoke_path.write_text(
        "word,count\nsales,40\nmargin,28\nnorth,22\n",
        encoding="utf-8",
    )
    wordcloud_result = AnalysisGraphService(paths).graph_dataset(
        GraphDatasetInput(
            source_path=str(wordcloud_smoke_path.resolve()),
            dataset_name="Graph wordcloud smoke",
            wordcloud_spec={
                "title": "Graph wordcloud smoke",
                "width": 360,
                "height": 220,
            },
        )
    )
    wordcloud_svg = Path(wordcloud_result.output_path).read_text(encoding="utf-8")
    if "<title>sales: 40</title>" not in wordcloud_svg or "Graph wordcloud smoke" not in wordcloud_svg:
        raise RuntimeError("Wordcloud smoke render failed.")

    xgboost_estimator = XGBoostRegressionService._build_estimator(
        n_estimators=2,
        max_depth=1,
        learning_rate=0.5,
    )
    xgboost_estimator.fit([[0.0], [1.0], [2.0], [3.0]], [0.0, 1.0, 2.0, 3.0])
    xgboost_prediction = xgboost_estimator.predict([[1.5]])
    if len(xgboost_prediction) != 1:
        raise RuntimeError("XGBoost packaged runtime smoke fit failed.")

    from .services.forecast_packaged_smoke import run_forecasting_packaged_smoke

    run_forecasting_packaged_smoke()

    from .services.recommendation_packaged_smoke import (
        run_recommendation_packaged_smoke,
    )

    run_recommendation_packaged_smoke()

    from .services.text_classification_packaged_smoke import (
        run_text_classification_packaged_smoke,
    )

    run_text_classification_packaged_smoke()

    from .services.text_discovery_packaged_smoke import (
        run_text_discovery_packaged_smoke,
    )

    run_text_discovery_packaged_smoke()

    from .services.knowledge_packaged_smoke import run_knowledge_packaged_smoke

    run_knowledge_packaged_smoke(paths)