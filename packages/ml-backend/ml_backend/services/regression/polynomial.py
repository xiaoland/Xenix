"""Polynomial Regression model"""

from typing import Any, Dict, List
import pandas as pd
import numpy as np
from sklearn.preprocessing import PolynomialFeatures
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

from .base import RegressionModelBase
from ...types import BatchTrainInput, SingleTrainInput


class PolynomialRegression(RegressionModelBase):
    """Polynomial Regression using Pipeline"""

    def get_model_class(self):
        """Return pipeline class (special handling)"""
        return Pipeline

    def get_default_params(self) -> Dict[str, Any]:
        return {"degree": 2}

    def get_param_grid(self) -> Dict[str, List[Any]]:
        return {
            "polynomialfeatures__degree": [2, 3, 4],
            "linearregression__fit_intercept": [True, False]
        }

    def _create_pipeline(self, degree: int = 2):
        """Create polynomial regression pipeline"""
        return Pipeline([
            ("polynomialfeatures", PolynomialFeatures(degree=degree)),
            ("linearregression", LinearRegression())
        ])

    def batch_train(
        self,
        df: pd.DataFrame,
        input_data: BatchTrainInput
    ) -> Dict[str, Any]:
        """Batch training with GridSearchCV for polynomial regression"""
        from sklearn.model_selection import GridSearchCV

        # Prepare data
        X = df[input_data.feature_columns]
        y = df[input_data.target_column]

        # Split train/test
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        # Create pipeline
        pipeline = self._create_pipeline()

        # Merge user param_grid with model's default param_grid
        param_grid = self.get_param_grid()
        if input_data.param_grid:
            param_grid = {**param_grid, **input_data.param_grid}

        # Run GridSearchCV
        grid_search = GridSearchCV(
            pipeline,
            param_grid,
            cv=5,
            scoring='r2',
            n_jobs=-1,
            verbose=1
        )

        grid_search.fit(X_train, y_train)

        # Get best model
        best_model = grid_search.best_estimator_
        best_params = grid_search.best_params_

        # Evaluate on test set
        y_pred = best_model.predict(X_test)

        metrics = {
            'r2': float(r2_score(y_test, y_pred)),
            'mse': float(mean_squared_error(y_test, y_pred)),
            'mae': float(mean_absolute_error(y_test, y_pred)),
            'rmse': float(np.sqrt(mean_squared_error(y_test, y_pred))),
            'cv_score_mean': float(grid_search.best_score_),
            'cv_scores': [float(s) for s in grid_search.cv_results_['mean_test_score']]
        }

        return {
            'best_params': best_params,
            'metrics': metrics,
            'model': best_model
        }

    def single_train(
        self,
        df: pd.DataFrame,
        input_data: SingleTrainInput
    ) -> Dict[str, Any]:
        """Single training for polynomial regression"""
        # Prepare data
        X = df[input_data.feature_columns]
        y = df[input_data.target_column]

        # Split train/test
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        # Get degree from params
        degree = input_data.params.get("degree", 2) if input_data.params else 2

        # Create and train pipeline
        pipeline = self._create_pipeline(degree=degree)
        pipeline.fit(X_train, y_train)

        # Evaluate on test set
        y_pred = pipeline.predict(X_test)

        metrics = {
            'r2': float(r2_score(y_test, y_pred)),
            'mse': float(mean_squared_error(y_test, y_pred)),
            'mae': float(mean_absolute_error(y_test, y_pred)),
            'rmse': float(np.sqrt(mean_squared_error(y_test, y_pred)))
        }

        return {
            'metrics': metrics,
            'model': pipeline
        }

    def predict(
        self,
        train_df: pd.DataFrame,
        predict_df: pd.DataFrame,
        input_data
    ) -> pd.DataFrame:
        """Make predictions using polynomial regression"""
        # Train model
        X_train = train_df[input_data.feature_columns]
        y_train = train_df[input_data.target_column]

        # Get degree from params
        degree = input_data.params.get("degree", 2) if input_data.params else 2

        # Create and train pipeline
        pipeline = self._create_pipeline(degree=degree)
        pipeline.fit(X_train, y_train)

        # Make predictions
        X_predict = predict_df[input_data.feature_columns]
        predictions = pipeline.predict(X_predict)

        # Add predictions to dataframe
        predict_df = predict_df.copy()
        predict_df[f'predicted_{input_data.target_column}'] = predictions

        return predict_df
