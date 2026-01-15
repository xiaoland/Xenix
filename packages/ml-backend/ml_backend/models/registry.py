"""Model registry - 12 regression models"""

from typing import Any, Dict, List
from sklearn.linear_model import (
    LinearRegression,
    Ridge,
    Lasso,
    BayesianRidge
)
from sklearn.neighbors import KNeighborsRegressor
from sklearn.tree import DecisionTreeRegressor
from sklearn.ensemble import (
    RandomForestRegressor,
    AdaBoostRegressor,
    GradientBoostingRegressor
)
from sklearn.preprocessing import PolynomialFeatures
from sklearn.pipeline import Pipeline
import xgboost as xgb
import lightgbm as lgb


# Model registry with default parameter grids for tuning
MODEL_REGISTRY: Dict[str, Dict[str, Any]] = {
    # Linear Models
    "regression.linear": {
        "class": LinearRegression,
        "name": "Linear Regression",
        "default_params": {},
        "param_grid": {
            "fit_intercept": [True, False],
            "positive": [True, False]
        }
    },
    "regression.ridge": {
        "class": Ridge,
        "name": "Ridge Regression",
        "default_params": {"alpha": 1.0},
        "param_grid": {
            "alpha": [0.1, 1.0, 10.0, 100.0],
            "solver": ["auto", "svd", "cholesky"]
        }
    },
    "regression.lasso": {
        "class": Lasso,
        "name": "Lasso Regression",
        "default_params": {"alpha": 1.0},
        "param_grid": {
            "alpha": [0.1, 1.0, 10.0, 100.0],
            "selection": ["cyclic", "random"]
        }
    },
    "regression.bayesian_ridge": {
        "class": BayesianRidge,
        "name": "Bayesian Ridge Regression",
        "default_params": {},
        "param_grid": {
            "alpha_1": [1e-6, 1e-5, 1e-4],
            "alpha_2": [1e-6, 1e-5, 1e-4],
            "lambda_1": [1e-6, 1e-5, 1e-4],
            "lambda_2": [1e-6, 1e-5, 1e-4]
        }
    },

    # Polynomial Regression (special case - uses pipeline)
    "regression.polynomial": {
        "class": "pipeline",  # Special handling
        "name": "Polynomial Regression",
        "default_params": {"degree": 2},
        "param_grid": {
            "polynomialfeatures__degree": [2, 3, 4],
            "linearregression__fit_intercept": [True, False]
        }
    },

    # K-Nearest Neighbors
    "regression.knn": {
        "class": KNeighborsRegressor,
        "name": "K-Nearest Neighbors",
        "default_params": {"n_neighbors": 5},
        "param_grid": {
            "n_neighbors": [3, 5, 7, 9],
            "weights": ["uniform", "distance"],
            "algorithm": ["auto", "ball_tree", "kd_tree"]
        }
    },

    # Tree-based Models
    "regression.decision_tree": {
        "class": DecisionTreeRegressor,
        "name": "Decision Tree",
        "default_params": {"max_depth": 5},
        "param_grid": {
            "max_depth": [3, 5, 7, 10, None],
            "min_samples_split": [2, 5, 10],
            "min_samples_leaf": [1, 2, 4]
        }
    },
    "regression.random_forest": {
        "class": RandomForestRegressor,
        "name": "Random Forest",
        "default_params": {"n_estimators": 100},
        "param_grid": {
            "n_estimators": [50, 100, 200],
            "max_depth": [5, 10, None],
            "min_samples_split": [2, 5, 10],
            "min_samples_leaf": [1, 2, 4]
        }
    },

    # Boosting Models
    "regression.adaboost": {
        "class": AdaBoostRegressor,
        "name": "AdaBoost",
        "default_params": {"n_estimators": 50},
        "param_grid": {
            "n_estimators": [50, 100, 200],
            "learning_rate": [0.01, 0.1, 1.0],
            "loss": ["linear", "square", "exponential"]
        }
    },
    "regression.gbdt": {
        "class": GradientBoostingRegressor,
        "name": "Gradient Boosting (GBDT)",
        "default_params": {"n_estimators": 100},
        "param_grid": {
            "n_estimators": [50, 100, 200],
            "learning_rate": [0.01, 0.1, 0.2],
            "max_depth": [3, 5, 7],
            "subsample": [0.8, 1.0]
        }
    },
    "regression.xgboost": {
        "class": xgb.XGBRegressor,
        "name": "XGBoost",
        "default_params": {"n_estimators": 100, "objective": "reg:squarederror"},
        "param_grid": {
            "n_estimators": [50, 100, 200],
            "learning_rate": [0.01, 0.1, 0.3],
            "max_depth": [3, 5, 7],
            "subsample": [0.8, 1.0],
            "colsample_bytree": [0.8, 1.0]
        }
    },
    "regression.lightgbm": {
        "class": lgb.LGBMRegressor,
        "name": "LightGBM",
        "default_params": {"n_estimators": 100},
        "param_grid": {
            "n_estimators": [50, 100, 200],
            "learning_rate": [0.01, 0.1, 0.3],
            "max_depth": [3, 5, 7, -1],
            "num_leaves": [31, 50, 100],
            "subsample": [0.8, 1.0]
        }
    }
}


def get_model(model_name: str, params: Dict[str, Any] = None):
    """
    Get a model instance by name

    Args:
        model_name: Model identifier (e.g., 'regression.ridge')
        params: Parameters to initialize the model with

    Returns:
        Model instance (sklearn estimator or pipeline)
    """
    if model_name not in MODEL_REGISTRY:
        raise ValueError(
            f"Unknown model: {model_name}. "
            f"Available models: {', '.join(MODEL_REGISTRY.keys())}"
        )

    config = MODEL_REGISTRY[model_name]
    model_params = params or config["default_params"]

    # Special case for polynomial regression (pipeline)
    if config["class"] == "pipeline":
        degree = model_params.get("degree", 2)
        return Pipeline([
            ("polynomialfeatures", PolynomialFeatures(degree=degree)),
            ("linearregression", LinearRegression())
        ])

    # Regular model
    model_class = config["class"]
    return model_class(**model_params)


def list_models() -> List[str]:
    """Get list of available model names"""
    return list(MODEL_REGISTRY.keys())


def get_param_grid(model_name: str) -> Dict[str, List[Any]]:
    """
    Get default parameter grid for a model

    Args:
        model_name: Model identifier

    Returns:
        Parameter grid for GridSearchCV
    """
    if model_name not in MODEL_REGISTRY:
        raise ValueError(f"Unknown model: {model_name}")

    return MODEL_REGISTRY[model_name]["param_grid"]
