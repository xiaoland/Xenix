# ============================================
# 0. Ignore Warning
# ============================================
import warnings
warnings.filterwarnings("ignore")

# ============================================
# 1. Helper functions
# ============================================
import os
import json

def load_params(json_filename):
    """Load params from JSON file; return empty dict if not found"""
    if os.path.exists(json_filename):
        with open(json_filename, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        print(f"⚠️ JSON file not found, using default params: {json_filename}")
        return {}

def add_prefix_for_pipeline(params, prefix="model"):
    """Add model__ prefix for pipeline parameters (Pipeline models)"""
    if not params:
        return params
    new_params = {}
    for k, v in params.items():
        if "__" not in k:
            new_params[f"{prefix}__{k}"] = v
        else:
            new_params[k] = v
    return new_params

# ============================================
# 2. JSON files mapping
# ============================================
json_files = {
    "LinearRegression": "Linear_Regression_Hyperparameter_Tuning_Params.json",
    "Ridge": "Ridge_Params.json",
    "Lasso": "Lasso_Params.json",
    "BayesianRidge": "Bayesian_Ridge_Regression_Params.json",
    "KNN": "K-Nearest_Neighbors_Params.json",
    "DecisionTree": "Regression_Decision_Tree_Params.json",
    "RandomForest": "Random_Forest_Params.json",
    "GBDT": "GBDT_Params.json",
    "AdaBoost": "AdaBoost_Params.json",
    "XGBoost": "XGBoost_Params.json",
    "LightGBM": "LightGBM_Params.json",
    "PolynomialRegression": "Polynomial_Regression_Params.json"
}

# Load all JSON parameter files
model_params = {name: load_params(path) for name, path in json_files.items()}


# ============================================
# 3. Read data
# ============================================
import pandas as pd

df = pd.read_excel("Customer Value Data Table.xlsx")

X = df[['Historical Loan Amount',
        'Number of Loans',
        'Education',
        'Monthly Income',
        'Gender']]
y = df['Customer Value']


# ============================================
# 4. Train-test split
# ============================================
from sklearn.model_selection import train_test_split

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)


# ============================================
# 5. Build 12 regression models
# ============================================
from sklearn.linear_model import LinearRegression, Ridge, Lasso, BayesianRidge
from sklearn.tree import DecisionTreeRegressor
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor, AdaBoostRegressor
from sklearn.neighbors import KNeighborsRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, PolynomialFeatures

from xgboost import XGBRegressor
from lightgbm import LGBMRegressor

models = {}

# 1. Linear Regression
params = add_prefix_for_pipeline(model_params["LinearRegression"])
lin_model = Pipeline([
    ("scaler", StandardScaler()),
    ("model", LinearRegression())
])
lin_model.set_params(**params)
models["LinearRegression"] = lin_model

# 2. Ridge Regression
params = add_prefix_for_pipeline(model_params["Ridge"])
ridge_model = Pipeline([
    ("scaler", StandardScaler()),
    ("model", Ridge(random_state=42))
])
ridge_model.set_params(**params)
models["Ridge"] = ridge_model

# 3. Lasso Regression
params = add_prefix_for_pipeline(model_params["Lasso"])
lasso_model = Pipeline([
    ("scaler", StandardScaler()),
    ("model", Lasso(random_state=42))
])
lasso_model.set_params(**params)
models["Lasso"] = lasso_model

# 4. Bayesian Ridge Regression
params = add_prefix_for_pipeline(model_params["BayesianRidge"])
bayes_model = Pipeline([
    ("scaler", StandardScaler()),
    ("model", BayesianRidge())
])
bayes_model.set_params(**params)
models["BayesianRidge"] = bayes_model

# 5. KNN Regression
params = add_prefix_for_pipeline(model_params["KNN"])
knn_model = Pipeline([
    ("scaler", StandardScaler()),
    ("model", KNeighborsRegressor())
])
knn_model.set_params(**params)
models["KNN"] = knn_model

# 6. Decision Tree
models["DecisionTree"] = DecisionTreeRegressor(
    **model_params["DecisionTree"],
    random_state=42
)

# 7. Random Forest
models["RandomForest"] = RandomForestRegressor(
    **model_params["RandomForest"],
    random_state=42,
    n_jobs=-1
)

# 8. GBDT (Gradient Boosting)
models["GBDT"] = GradientBoostingRegressor(
    **model_params["GBDT"],
    random_state=42
)

# 9. AdaBoost
ada_json = model_params["AdaBoost"]

tree_params = {}
ada_params_clean = {}

for k, v in ada_json.items():
    if k.startswith("estimator__"):
        tree_params[k.replace("estimator__", "")] = v
    else:
        ada_params_clean[k] = v

models["AdaBoost"] = AdaBoostRegressor(
    estimator=DecisionTreeRegressor(**tree_params),
    **ada_params_clean,
    random_state=42
)

# 10. XGBoost
xgb_params = model_params["XGBoost"]
models["XGBoost"] = XGBRegressor(
    **xgb_params,
    objective="reg:squarederror",
    random_state=42,
    n_jobs=-1
)

# 11. LightGBM
lgb_params = model_params["LightGBM"]
models["LightGBM"] = LGBMRegressor(
    **lgb_params,
    objective="regression",
    random_state=42,
    n_jobs=-1,
    verbose=-1,
    verbosity=-1,
    silent=True
)

# 12. Polynomial Regression
poly_params = model_params["PolynomialRegression"]
degree = poly_params.get("degree", 2)

poly_model = Pipeline([
    ("poly", PolynomialFeatures(degree=degree, include_bias=False)),
    ("scaler", StandardScaler()),
    ("model", LinearRegression())
])

models["PolynomialRegression"] = poly_model


# ============================================
# 6. Train & evaluate models
# ============================================
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

results = []

for name, model in models.items():
    print(f"\nTraining model: {name} ...")
    model.fit(X_train, y_train)

    y_train_pred = model.predict(X_train)
    y_test_pred = model.predict(X_test)

    results.append({
        "Model": name,
        "MSE_train": mean_squared_error(y_train, y_train_pred),
        "MAE_train": mean_absolute_error(y_train, y_train_pred),
        "R2_train": r2_score(y_train, y_train_pred),
        "MSE_test": mean_squared_error(y_test, y_test_pred),
        "MAE_test": mean_absolute_error(y_test, y_test_pred),
        "R2_test": r2_score(y_test, y_test_pred)
    })


# ============================================
# 7. Show comparison table
# ============================================
results_df = pd.DataFrame(results)
results_df = results_df.sort_values(by="R2_test", ascending=False)

print("\n=== Regression Models Comparison (12 Models) ===")
print(results_df.to_string(index=False))

# Optional export
results_df.to_excel("Model_Comparison_12_Models.xlsx", index=False)
