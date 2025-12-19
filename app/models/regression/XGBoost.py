# ============================================
# 0. Ignore Warning
# ============================================
import warnings
warnings.filterwarnings("ignore")

# ============================================
# 1. Read data
# ============================================
import pandas as pd

input_file = 'Customer Value Data Table.xlsx'
df = pd.read_excel(input_file)

# Set the independent variable and the dependent variable
X = df[['Historical Loan Amount',
        'Number of Loans',
        'Education',
        'Monthly Income',
        'Gender']]
y = df['Customer Value']

# ============================================
# 2. Train-test split
# ============================================
from sklearn.model_selection import train_test_split

X_train, X_test, y_train, y_test = train_test_split(
    X, y,
    test_size=0.2,      # 20% as test set
    random_state=42     # for reproducibility
)

# ============================================
# 3. Hyperparameter Tuning (Grid Search on training set)
#    Model: XGBoost Regressor
# ============================================
from xgboost import XGBRegressor
from sklearn.model_selection import GridSearchCV

# Define base model
base_model = XGBRegressor(
    objective="reg:squarederror",
    random_state=42,
    n_jobs=-1
)

# Define parameter grid (main tuning parameters for XGBoost)
param_grid = {
    "n_estimators": [100, 200, 300],          # number of trees
    "learning_rate": [0.01, 0.05, 0.1, 0.2], # step size shrinkage
    "max_depth": [3, 4, 5],                   # max depth of a tree
    "subsample": [0.8, 1.0],                  # row sampling
    "colsample_bytree": [0.8, 1.0],           # feature sampling per tree
    "reg_lambda": [1.0, 5.0, 10.0]            # L2 regularization term
}

# Grid Search with 5-fold cross validation, using negative MSE as scoring
grid_search = GridSearchCV(
    estimator=base_model,
    param_grid=param_grid,
    cv=5,
    scoring="neg_mean_squared_error",
    n_jobs=-1
)

# Run grid search on training set
grid_search.fit(X_train, y_train)

# Show best parameters (from CV on training set)
print("Best Parameters (from GridSearchCV):", grid_search.best_params_)
print("Best CV Score (Negative MSE):", grid_search.best_score_)

# Best model (already fitted on training data)
best_model = grid_search.best_estimator_

# ============================================
# 4. Evaluate best model on training & test set
# ============================================
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

# ---- On training set ----
y_train_pred = best_model.predict(X_train)
mse_train = mean_squared_error(y_train, y_train_pred)
mae_train = mean_absolute_error(y_train, y_train_pred)
r2_train = r2_score(y_train, y_train_pred)

print("\n=== Training Set Performance ===")
print("MSE (train):", mse_train)
print("MAE (train):", mae_train)
print("R-squared (train):", r2_train)

# ---- On test set ----
y_test_pred = best_model.predict(X_test)
mse_test = mean_squared_error(y_test, y_test_pred)
mae_test = mean_absolute_error(y_test, y_test_pred)
r2_test = r2_score(y_test, y_test_pred)

print("\n=== Test Set Performance ===")
print("MSE (test):", mse_test)
print("MAE (test):", mae_test)
print("R-squared (test):", r2_test)

# Single sample prediction example (using the current best_model)
print("\nSingle Sample Prediction (using best_model on train):",
      best_model.predict([[6488, 2, 2, 9567, 1]]))

# ============================================
# 5. Retrain final model on ALL data using best params
#    (Used for production deployment / predicting new files)
# ============================================
best_params = grid_search.best_params_

final_model = XGBRegressor(
    objective="reg:squarederror",
    random_state=42,
    n_jobs=-1,
    **best_params
)
final_model.fit(X, y)

print("\nFinal XGBoost model trained on ALL data with best params:", best_params)

# Single sample prediction with final model
print("Single Sample Prediction (final_model on ALL data):",
      final_model.predict([[6488, 2, 2, 9567, 1]]))

# ============================================
# 6. Use final_model to predict new file and save output
# ============================================

# 1. Specify feature column names (must match the headers in XXX.xlsx)
feature_cols = ['Historical Loan Amount',
                'Number of Loans',
                'Education',
                'Monthly Income',
                'Gender']

# 2. Read the new file "XXX.xlsx" for prediction
pre_file = 'Customer Value Data Table - test.xlsx'
new_df = pd.read_excel(pre_file)

# 3. Extract feature matrix X_new
X_new = new_df[feature_cols]

# 4. Use the final model to make predictions
y_new_pred = final_model.predict(X_new)

# 5. Add prediction results into new_df as a new column
new_df['Predicted Customer Value'] = y_new_pred

# 6. Save as a new "XXX.xlsx"
output_file = 'output.xlsx'
new_df.to_excel(output_file, index=False)

print("\nPrediction completed with final XGBoost model. The file has been updated:", output_file)

# ============================================
# 7. Save hyperparameter tuning results to JSON
# ============================================
import json

json_file = "XGBoost_Params.json"

with open(json_file, "w", encoding="utf-8") as f:
    json.dump(best_params, f, indent=4)

print(f"\nHyperparameter tuning parameters have been saved to: {json_file}")