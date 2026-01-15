"""Base class for regression models"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List
import pandas as pd
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import numpy as np

from ...types import BatchTrainInput, BatchTrainOutput, SingleTrainInput, SingleTrainOutput


class RegressionModelBase(ABC):
    """
    Abstract base class for regression models

    Each regression model must implement:
    - get_model_class(): Return the sklearn model class
    - get_default_params(): Return default parameters
    - get_param_grid(): Return parameter grid for GridSearchCV
    """

    @abstractmethod
    def get_model_class(self):
        """Return the model class (e.g., Ridge, Lasso, XGBRegressor)"""
        pass

    @abstractmethod
    def get_default_params(self) -> Dict[str, Any]:
        """Return default model parameters"""
        pass

    @abstractmethod
    def get_param_grid(self) -> Dict[str, List[Any]]:
        """Return parameter grid for GridSearchCV"""
        pass

    def batch_train(
        self,
        df: pd.DataFrame,
        input_data: BatchTrainInput
    ) -> Dict[str, Any]:
        """
        Batch training with GridSearchCV

        Args:
            df: Training dataframe
            input_data: Input parameters

        Returns:
            Dictionary with best_params, metrics, and model
        """
        # Prepare data
        X = df[input_data.feature_columns]
        y = df[input_data.target_column]

        # Split train/test
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        # Merge user param_grid with model's default param_grid
        param_grid = self.get_param_grid()
        if input_data.param_grid:
            # User-provided param_grid takes precedence
            param_grid = {**param_grid, **input_data.param_grid}

        # Create model and run GridSearchCV
        model_class = self.get_model_class()
        grid_search = GridSearchCV(
            model_class(),
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
        """
        Single training with specific parameters

        Args:
            df: Training dataframe
            input_data: Input parameters

        Returns:
            Dictionary with metrics and model
        """
        # Prepare data
        X = df[input_data.feature_columns]
        y = df[input_data.target_column]

        # Split train/test
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        # Merge user params with default params
        params = self.get_default_params()
        if input_data.params:
            params = {**params, **input_data.params}

        # Train model
        model_class = self.get_model_class()
        model = model_class(**params)
        model.fit(X_train, y_train)

        # Evaluate on test set
        y_pred = model.predict(X_test)

        metrics = {
            'r2': float(r2_score(y_test, y_pred)),
            'mse': float(mean_squared_error(y_test, y_pred)),
            'mae': float(mean_absolute_error(y_test, y_pred)),
            'rmse': float(np.sqrt(mean_squared_error(y_test, y_pred)))
        }

        return {
            'metrics': metrics,
            'model': model
        }

    def predict(
        self,
        train_df: pd.DataFrame,
        predict_df: pd.DataFrame,
        input_data
    ) -> pd.DataFrame:
        """
        Make predictions

        Args:
            train_df: Training dataframe
            predict_df: Prediction dataframe
            input_data: Input parameters with params

        Returns:
            Prediction dataframe with predictions added
        """
        # Train model
        X_train = train_df[input_data.feature_columns]
        y_train = train_df[input_data.target_column]

        # Merge user params with default params
        params = self.get_default_params()
        if input_data.params:
            params = {**params, **input_data.params}

        # Train model
        model_class = self.get_model_class()
        model = model_class(**params)
        model.fit(X_train, y_train)

        # Make predictions
        X_predict = predict_df[input_data.feature_columns]
        predictions = model.predict(X_predict)

        # Add predictions to dataframe
        predict_df = predict_df.copy()
        predict_df[f'predicted_{input_data.target_column}'] = predictions

        return predict_df
