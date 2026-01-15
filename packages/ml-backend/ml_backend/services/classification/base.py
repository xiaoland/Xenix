"""Base class for classification models"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List
import pandas as pd
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
import numpy as np

from ...types import BatchTrainInput, BatchTrainOutput, SingleTrainInput, SingleTrainOutput


class ClassificationModelBase(ABC):
    """
    Abstract base class for classification models

    Each classification model must implement:
    - get_model_class(): Return the sklearn model class
    - get_default_params(): Return default parameters
    - get_param_grid(): Return parameter grid for GridSearchCV
    """

    @abstractmethod
    def get_model_class(self):
        """Return the model class (e.g., LogisticRegression, RandomForestClassifier)"""
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
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        # Merge user param_grid with model's default param_grid
        param_grid = self.get_param_grid()
        if input_data.param_grid:
            param_grid = {**param_grid, **input_data.param_grid}

        # Create model and run GridSearchCV
        model_class = self.get_model_class()
        grid_search = GridSearchCV(
            model_class(),
            param_grid,
            cv=5,
            scoring='accuracy',
            n_jobs=-1,
            verbose=1
        )

        grid_search.fit(X_train, y_train)

        # Get best model
        best_model = grid_search.best_estimator_
        best_params = grid_search.best_params_

        # Evaluate on test set
        y_pred = best_model.predict(X_test)

        # Calculate metrics (handle binary and multi-class)
        n_classes = len(np.unique(y))
        avg_method = 'binary' if n_classes == 2 else 'weighted'

        metrics = {
            'accuracy': float(accuracy_score(y_test, y_pred)),
            'precision': float(precision_score(y_test, y_pred, average=avg_method, zero_division=0)),
            'recall': float(recall_score(y_test, y_pred, average=avg_method, zero_division=0)),
            'f1': float(f1_score(y_test, y_pred, average=avg_method, zero_division=0)),
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
            X, y, test_size=0.2, random_state=42, stratify=y
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

        # Calculate metrics (handle binary and multi-class)
        n_classes = len(np.unique(y))
        avg_method = 'binary' if n_classes == 2 else 'weighted'

        metrics = {
            'accuracy': float(accuracy_score(y_test, y_pred)),
            'precision': float(precision_score(y_test, y_pred, average=avg_method, zero_division=0)),
            'recall': float(recall_score(y_test, y_pred, average=avg_method, zero_division=0)),
            'f1': float(f1_score(y_test, y_pred, average=avg_method, zero_division=0))
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

        # Add prediction probabilities if available
        if hasattr(model, 'predict_proba'):
            proba = model.predict_proba(X_predict)
            for i, class_label in enumerate(model.classes_):
                predict_df[f'probability_class_{class_label}'] = proba[:, i]

        return predict_df
