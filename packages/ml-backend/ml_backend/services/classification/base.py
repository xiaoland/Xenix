"""Base class for classification models with type-safe parameter schemas"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, TypeVar, Union
import pandas as pd
from sklearn.base import BaseEstimator
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
import numpy as np
from pydantic import BaseModel

from ...types import BatchTrainInput, SingleTrainInput


# Type variable for model type
ModelType = TypeVar("ModelType", bound=Union[BaseEstimator, Pipeline])

# Type variable for parameter type
ModelParamType = TypeVar("ModelParamType", bound=BaseModel)

# Type variable for parameter grid type
ParamGridType = TypeVar("ParamGridType", bound=BaseModel)


class ClassificationModel(ABC, Generic[ModelType, ModelParamType, ParamGridType]):
    """
    Abstract base class for classification models.

    All classification model modules should implement this interface to ensure
    consistency across different model implementations.

    Type Parameters:
        ModelType: The specific sklearn model type (Pipeline or BaseEstimator subclass)
        ModelParamType: The parameter model type (pydantic BaseModel subclass)
        ParamGridType: The parameter grid model type (pydantic BaseModel subclass with list fields)
    """

    __paramgrid__: type[ParamGridType]
    __modelparam__: type[ModelParamType]

    def __init_subclass__(
        cls,
        param_grid: type["ParamGridType"] = None,
        model_param: type["ModelParamType"] = None,
        **kwargs,
    ):
        """
        Hook to enforce schema registration when a concrete model class is defined.

        All concrete model classes must provide param_grid and model_param parameters
        when subclassing.

        Args:
            param_grid: The pydantic model class for parameter grids (with list fields)
            model_param: The pydantic model class for single parameters
        """
        super().__init_subclass__(**kwargs)
        if param_grid is not None:
            cls.__paramgrid__ = param_grid
        if model_param is not None:
            cls.__modelparam__ = model_param

    @abstractmethod
    def create_model(self, params: ModelParamType) -> ModelType:
        """
        Create model instance with given parameters

        Args:
            params: Model parameters (validated Pydantic model)

        Returns:
            Instantiated model
        """
        pass

    def get_default_params(self) -> ModelParamType:
        """
        Get default model parameters

        Returns:
            Default parameters as Pydantic model
        """
        return self.__modelparam__()

    def get_default_param_grid(self) -> ParamGridType:
        """
        Get default parameter grid for GridSearchCV

        Returns:
            Default parameter grid as Pydantic model
        """
        return self.__paramgrid__()

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

        # Get default param grid and merge with user-provided grid
        default_grid = self.get_default_param_grid()
        param_grid_dict = default_grid.model_dump()

        # Merge user param_grid
        if input_data.param_grid:
            param_grid_dict = {**param_grid_dict, **input_data.param_grid}

        # Create base model with default params
        base_model = self.create_model(self.get_default_params())

        # Run GridSearchCV
        grid_search = GridSearchCV(
            base_model,
            param_grid_dict,
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

        # Get default params and merge with user params
        default_params = self.get_default_params()
        params_dict = default_params.model_dump()

        if input_data.params:
            params_dict = {**params_dict, **input_data.params}

        # Validate and create params model
        params = self.__modelparam__(**params_dict)

        # Create and train model
        model = self.create_model(params)
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

        # Get default params and merge with user params
        default_params = self.get_default_params()
        params_dict = default_params.model_dump()

        if input_data.params:
            params_dict = {**params_dict, **input_data.params}

        # Validate and create params model
        params = self.__modelparam__(**params_dict)

        # Create and train model
        model = self.create_model(params)
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


# Backwards compatibility alias
ClassificationModelBase = ClassificationModel
