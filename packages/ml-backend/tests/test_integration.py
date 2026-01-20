"""
Integration tests for all ML models with Pydantic schema validation

Tests cover:
- Model instantiation
- Default params and param grids
- Model creation
- Training (batch_train, single_train)
- Prediction
- Pydantic validation
"""

import pytest
import pandas as pd
import numpy as np
from typing import Type, Any

# Regression models
from ml_backend.services.regression.linear import LinearRegressionModel
from ml_backend.services.regression.ridge import RidgeRegression
from ml_backend.services.regression.lasso import LassoRegression
from ml_backend.services.regression.bayesian_ridge import BayesianRidgeRegression
from ml_backend.services.regression.polynomial import PolynomialRegression
from ml_backend.services.regression.knn import KNNRegression
from ml_backend.services.regression.decision_tree import DecisionTreeRegression
from ml_backend.services.regression.random_forest import RandomForestRegression
from ml_backend.services.regression.adaboost import AdaBoostRegression
from ml_backend.services.regression.gbdt import GBDTRegression
from ml_backend.services.regression.xgboost import XGBoostRegression
from ml_backend.services.regression.lightgbm import LightGBMRegression

# Classification models
from ml_backend.services.classification.logistic_regression import LogisticRegressionClassifier
from ml_backend.services.classification.random_forest import RandomForestClassification

from ml_backend.types import BatchTrainInput, SingleTrainInput, PredictInput


# Test data fixtures
@pytest.fixture
def regression_data():
    """Generate synthetic regression data"""
    np.random.seed(42)
    n_samples = 200
    n_features = 5

    X = np.random.randn(n_samples, n_features)
    # Linear relationship with some noise
    true_coef = np.array([2.0, -3.0, 1.5, 0.5, -1.0])
    y = X @ true_coef + np.random.randn(n_samples) * 0.5

    # Create DataFrame
    feature_cols = [f"feature_{i}" for i in range(n_features)]
    df = pd.DataFrame(X, columns=feature_cols)
    df["target"] = y

    return df, feature_cols, "target"


@pytest.fixture
def classification_data():
    """Generate synthetic classification data"""
    np.random.seed(42)
    n_samples = 200
    n_features = 5

    X = np.random.randn(n_samples, n_features)
    # Binary classification with decision boundary
    y = ((X[:, 0] + X[:, 1]) > 0).astype(int)

    # Create DataFrame
    feature_cols = [f"feature_{i}" for i in range(n_features)]
    df = pd.DataFrame(X, columns=feature_cols)
    df["target"] = y

    return df, feature_cols, "target"


# Regression model test parameters
REGRESSION_MODELS = [
    (LinearRegressionModel, "Linear Regression"),
    (RidgeRegression, "Ridge Regression"),
    (LassoRegression, "Lasso Regression"),
    (BayesianRidgeRegression, "Bayesian Ridge"),
    (PolynomialRegression, "Polynomial Regression"),
    (KNNRegression, "KNN Regression"),
    (DecisionTreeRegression, "Decision Tree"),
    (RandomForestRegression, "Random Forest"),
    (AdaBoostRegression, "AdaBoost"),
    (GBDTRegression, "GBDT"),
    (XGBoostRegression, "XGBoost"),
    (LightGBMRegression, "LightGBM"),
]

CLASSIFICATION_MODELS = [
    (LogisticRegressionClassifier, "Logistic Regression"),
    (RandomForestClassification, "Random Forest Classifier"),
]


class TestModelInstantiation:
    """Test that all models can be instantiated"""

    @pytest.mark.parametrize("model_class,name", REGRESSION_MODELS)
    def test_regression_model_instantiation(self, model_class, name):
        """Test regression model instantiation"""
        model = model_class()
        assert model is not None, f"{name} failed to instantiate"

    @pytest.mark.parametrize("model_class,name", CLASSIFICATION_MODELS)
    def test_classification_model_instantiation(self, model_class, name):
        """Test classification model instantiation"""
        model = model_class()
        assert model is not None, f"{name} failed to instantiate"


class TestModelSchemas:
    """Test Pydantic schemas for all models"""

    @pytest.mark.parametrize("model_class,name", REGRESSION_MODELS)
    def test_regression_default_params(self, model_class, name):
        """Test that models have valid default params"""
        model = model_class()
        params = model.get_default_params()

        # Should be a Pydantic model
        assert hasattr(params, 'model_dump'), f"{name} params should be Pydantic BaseModel"

        # Should be able to dump to dict
        params_dict = params.model_dump()
        assert isinstance(params_dict, dict), f"{name} params should dump to dict"
        assert len(params_dict) > 0, f"{name} should have at least one parameter"

    @pytest.mark.parametrize("model_class,name", REGRESSION_MODELS)
    def test_regression_param_grids(self, model_class, name):
        """Test that models have valid parameter grids"""
        model = model_class()
        param_grid = model.get_default_param_grid()

        # Should be a Pydantic model
        assert hasattr(param_grid, 'model_dump'), f"{name} param grid should be Pydantic BaseModel"

        # Should dump to dict with list values
        grid_dict = param_grid.model_dump()
        assert isinstance(grid_dict, dict), f"{name} param grid should dump to dict"
        assert len(grid_dict) > 0, f"{name} should have at least one parameter in grid"

        # All values should be lists (for GridSearchCV)
        for key, value in grid_dict.items():
            assert isinstance(value, list), f"{name} param grid '{key}' should be a list"

    @pytest.mark.parametrize("model_class,name", CLASSIFICATION_MODELS)
    def test_classification_default_params(self, model_class, name):
        """Test classification model default params"""
        model = model_class()
        params = model.get_default_params()
        params_dict = params.model_dump()
        assert isinstance(params_dict, dict) and len(params_dict) > 0

    @pytest.mark.parametrize("model_class,name", CLASSIFICATION_MODELS)
    def test_classification_param_grids(self, model_class, name):
        """Test classification model param grids"""
        model = model_class()
        param_grid = model.get_default_param_grid()
        grid_dict = param_grid.model_dump()
        assert isinstance(grid_dict, dict) and len(grid_dict) > 0


class TestModelCreation:
    """Test model creation with parameters"""

    @pytest.mark.parametrize("model_class,name", REGRESSION_MODELS)
    def test_regression_create_model(self, model_class, name):
        """Test creating sklearn model instances"""
        model = model_class()
        params = model.get_default_params()
        sklearn_model = model.create_model(params)

        assert sklearn_model is not None, f"{name} create_model returned None"
        # Should have fit and predict methods (sklearn API)
        assert hasattr(sklearn_model, 'fit'), f"{name} model should have fit method"
        assert hasattr(sklearn_model, 'predict'), f"{name} model should have predict method"

    @pytest.mark.parametrize("model_class,name", CLASSIFICATION_MODELS)
    def test_classification_create_model(self, model_class, name):
        """Test creating classification model instances"""
        model = model_class()
        params = model.get_default_params()
        sklearn_model = model.create_model(params)

        assert sklearn_model is not None
        assert hasattr(sklearn_model, 'fit')
        assert hasattr(sklearn_model, 'predict')


class TestSingleTraining:
    """Test single training for all models"""

    @pytest.mark.parametrize("model_class,name", REGRESSION_MODELS)
    def test_regression_single_train(self, model_class, name, regression_data):
        """Test single training on regression models"""
        df, feature_cols, target_col = regression_data
        model = model_class()

        input_data = SingleTrainInput(
            task_id=1,
            input_file="test.csv",
            model=name,
            feature_columns=feature_cols,
            target_column=target_col,
            params={}  # Use defaults
        )

        result = model.single_train(df, input_data)

        # Check result structure
        assert 'metrics' in result, f"{name} should return metrics"
        assert 'model' in result, f"{name} should return trained model"

        # Check metrics
        metrics = result['metrics']
        assert 'r2' in metrics, f"{name} should have R² metric"
        assert 'mse' in metrics, f"{name} should have MSE metric"
        assert 'mae' in metrics, f"{name} should have MAE metric"
        assert 'rmse' in metrics, f"{name} should have RMSE metric"

        # R² should be reasonable (not perfect due to noise, but positive)
        assert -1.0 <= metrics['r2'] <= 1.0, f"{name} R² should be between -1 and 1"

        # MSE should be positive
        assert metrics['mse'] > 0, f"{name} MSE should be positive"

        print(f"✓ {name}: R²={metrics['r2']:.4f}, MSE={metrics['mse']:.4f}")

    @pytest.mark.parametrize("model_class,name", CLASSIFICATION_MODELS)
    def test_classification_single_train(self, model_class, name, classification_data):
        """Test single training on classification models"""
        df, feature_cols, target_col = classification_data
        model = model_class()

        input_data = SingleTrainInput(
            task_id=1,
            input_file="test.csv",
            model=name,
            feature_columns=feature_cols,
            target_column=target_col,
            params={}
        )

        result = model.single_train(df, input_data)

        # Check result structure
        assert 'metrics' in result
        assert 'model' in result

        # Check metrics
        metrics = result['metrics']
        assert 'accuracy' in metrics
        assert 'precision' in metrics
        assert 'recall' in metrics
        assert 'f1' in metrics

        # Accuracy should be between 0 and 1
        assert 0.0 <= metrics['accuracy'] <= 1.0, f"{name} accuracy should be between 0 and 1"

        print(f"✓ {name}: Accuracy={metrics['accuracy']:.4f}, F1={metrics['f1']:.4f}")


class TestBatchTraining:
    """Test batch training (GridSearchCV) for models"""

    # Test a subset for batch training (it's slower)
    @pytest.mark.parametrize("model_class,name", [
        (LinearRegressionModel, "Linear Regression"),
        (RidgeRegression, "Ridge Regression"),
        (DecisionTreeRegression, "Decision Tree"),
    ])
    def test_regression_batch_train(self, model_class, name, regression_data):
        """Test batch training with GridSearchCV"""
        df, feature_cols, target_col = regression_data
        model = model_class()

        input_data = BatchTrainInput(
            task_id=1,
            input_file="test.csv",
            model=name,
            feature_columns=feature_cols,
            target_column=target_col,
            param_grid={}  # Use defaults
        )

        result = model.batch_train(df, input_data)

        # Check result structure
        assert 'best_params' in result
        assert 'metrics' in result
        assert 'model' in result

        # Check best_params
        assert isinstance(result['best_params'], dict)

        # Check metrics
        metrics = result['metrics']
        assert 'r2' in metrics
        assert 'cv_score_mean' in metrics
        assert 'cv_scores' in metrics

        # CV scores should be a list
        assert isinstance(metrics['cv_scores'], list)

        print(f"✓ {name} Batch: R²={metrics['r2']:.4f}, CV={metrics['cv_score_mean']:.4f}")

    @pytest.mark.parametrize("model_class,name", CLASSIFICATION_MODELS)
    def test_classification_batch_train(self, model_class, name, classification_data):
        """Test batch training for classification"""
        df, feature_cols, target_col = classification_data
        model = model_class()

        input_data = BatchTrainInput(
            task_id=1,
            input_file="test.csv",
            model=name,
            feature_columns=feature_cols,
            target_column=target_col,
            param_grid={}
        )

        result = model.batch_train(df, input_data)

        assert 'best_params' in result
        assert 'metrics' in result
        assert isinstance(result['metrics']['cv_scores'], list)

        print(f"✓ {name} Batch: Acc={result['metrics']['accuracy']:.4f}")


class TestPrediction:
    """Test prediction functionality"""

    @pytest.mark.parametrize("model_class,name", [
        (LinearRegressionModel, "Linear Regression"),
        (RidgeRegression, "Ridge Regression"),
        (RandomForestRegression, "Random Forest"),
    ])
    def test_regression_predict(self, model_class, name, regression_data):
        """Test prediction on new data"""
        df, feature_cols, target_col = regression_data

        # Split into train/predict
        train_df = df.iloc[:150]
        predict_df = df.iloc[150:].copy()
        predict_df = predict_df.drop(columns=[target_col])  # Remove target

        model = model_class()

        input_data = PredictInput(
            task_id=1,
            train_data="train.csv",
            predict_data="predict.csv",
            output_path="output.csv",
            model=name,
            feature_columns=feature_cols,
            target_column=target_col,
            params={}
        )

        result_df = model.predict(train_df, predict_df, input_data)

        # Check predictions were added
        pred_col = f'predicted_{target_col}'
        assert pred_col in result_df.columns, f"{name} should add prediction column"

        # Check predictions are numeric
        assert result_df[pred_col].dtype in [np.float64, np.float32, np.int64]

        # Check we have predictions for all rows
        assert len(result_df) == len(predict_df)
        assert result_df[pred_col].notna().all(), f"{name} should not have NaN predictions"

        print(f"✓ {name} Predict: {len(result_df)} predictions made")

    @pytest.mark.parametrize("model_class,name", CLASSIFICATION_MODELS)
    def test_classification_predict(self, model_class, name, classification_data):
        """Test classification prediction with probabilities"""
        df, feature_cols, target_col = classification_data

        train_df = df.iloc[:150]
        predict_df = df.iloc[150:].copy()
        predict_df = predict_df.drop(columns=[target_col])

        model = model_class()

        input_data = PredictInput(
            task_id=1,
            train_data="train.csv",
            predict_data="predict.csv",
            output_path="output.csv",
            model=name,
            feature_columns=feature_cols,
            target_column=target_col,
            params={}
        )

        result_df = model.predict(train_df, predict_df, input_data)

        # Check predictions
        pred_col = f'predicted_{target_col}'
        assert pred_col in result_df.columns

        # Check probability columns were added
        prob_cols = [col for col in result_df.columns if col.startswith('probability_class_')]
        assert len(prob_cols) > 0, f"{name} should add probability columns"

        print(f"✓ {name} Predict: {len(result_df)} predictions, {len(prob_cols)} probability columns")


class TestPydanticValidation:
    """Test that Pydantic validation works correctly"""

    def test_invalid_params_rejected(self):
        """Test that invalid parameters are rejected"""
        # Test with KNN which has proper constraints
        from ml_backend.services.regression.knn import KNNParams

        # Try to create params with invalid value (n_neighbors < 1)
        with pytest.raises(Exception):  # Pydantic will raise ValidationError
            KNNParams(n_neighbors=0)  # Should fail: n_neighbors must be >= 1

    def test_param_constraints(self):
        """Test parameter constraints are enforced"""
        from ml_backend.services.regression.knn import KNNParams

        # Valid params
        params = KNNParams(n_neighbors=5)
        assert params.n_neighbors == 5

        # Invalid: n_neighbors must be >= 1
        with pytest.raises(Exception):
            KNNParams(n_neighbors=0)

    def test_literal_constraints(self):
        """Test Literal type constraints"""
        from ml_backend.services.regression.ridge import RidgeParams

        # Valid solver
        params = RidgeParams(solver="auto")
        assert params.solver == "auto"

        # Invalid solver (not in Literal options)
        with pytest.raises(Exception):
            RidgeParams(solver="invalid_solver")


class TestModelRegistration:
    """Test that models have properly registered schemas"""

    @pytest.mark.parametrize("model_class,name", REGRESSION_MODELS)
    def test_regression_schema_registration(self, model_class, name):
        """Test that __paramgrid__ and __modelparam__ are registered"""
        model = model_class()

        assert hasattr(model, '__paramgrid__'), f"{name} should have __paramgrid__"
        assert hasattr(model, '__modelparam__'), f"{name} should have __modelparam__"

        # Check they are classes (not instances)
        assert isinstance(model.__paramgrid__, type), f"{name} __paramgrid__ should be a class"
        assert isinstance(model.__modelparam__, type), f"{name} __modelparam__ should be a class"

    @pytest.mark.parametrize("model_class,name", CLASSIFICATION_MODELS)
    def test_classification_schema_registration(self, model_class, name):
        """Test classification model schema registration"""
        model = model_class()
        assert hasattr(model, '__paramgrid__')
        assert hasattr(model, '__modelparam__')


# Summary test to print all model status
def test_all_models_summary(regression_data, classification_data):
    """Print summary of all models"""
    print("\n" + "="*70)
    print("INTEGRATION TEST SUMMARY")
    print("="*70)

    print("\n📊 REGRESSION MODELS (12):")
    for model_class, name in REGRESSION_MODELS:
        model = model_class()
        params = model.get_default_params()
        print(f"  ✓ {name:30s} - {len(params.model_dump())} parameters")

    print("\n🎯 CLASSIFICATION MODELS (2):")
    for model_class, name in CLASSIFICATION_MODELS:
        model = model_class()
        params = model.get_default_params()
        print(f"  ✓ {name:30s} - {len(params.model_dump())} parameters")

    print("\n" + "="*70)
    print("All models successfully migrated to type-safe Pydantic schemas!")
    print("="*70 + "\n")
