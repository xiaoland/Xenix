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
#    Model: Linear Regression + Standardization
# ============================================
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import GridSearchCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

# Pipeline: StandardScaler -> LinearRegression
base_model = Pipeline([
    ("scaler", StandardScaler()),
    ("model", LinearRegression())
])

# LinearRegression has very few tunable parameters,
# so we use fit_intercept as a simple example for hyperparameter tuning.
param_grid = {
    "model__fit_intercept": [True, False]
}

grid_search = GridSearchCV(
    estimator=base_model,
    param_grid=param_grid,
    cv=5,
    scoring="neg_mean_squared_error",
    n_jobs=-1
)

# Run grid search on training set
grid_search.fit(X_train, y_train)

# Show best parameters
print("Best Parameters (from GridSearchCV):", grid_search.best_params_)
print("Best CV Score (Negative MSE):", grid_search.best_score_)

# Best model (already fitted on training data)
best_model = grid_search.best_estimator_

# ============================================
# 4. Model evaluation (train & test)
# ============================================
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

# ---- On training set ----
y_train_pred = best_model.predict(X_train)
mse_train = mean_squared_error(y_train, y_train_pred)
mae_train = mean_absolute_error(y_train, y_train_pred)
r2_train = r2_score(y_train, y_train_pred)

print("\n=== Training Set Performance ===")
print("Mean Squared Error (train):", mse_train)
print("Mean Absolute Error (train):", mae_train)
print("Coefficient of Determination R-squared (train):", r2_train)

# ---- On test set ----
y_test_pred = best_model.predict(X_test)
mse_test = mean_squared_error(y_test, y_test_pred)
mae_test = mean_absolute_error(y_test, y_test_pred)
r2_test = r2_score(y_test, y_test_pred)

print("\n=== Test Set Performance ===")
print("Mean Squared Error (test):", mse_test)
print("Mean Absolute Error (test):", mae_test)
print("Coefficient of Determination R-squared (test):", r2_test)

# ============================================
# 5. Single sample prediction example (using best_model on train)
# ============================================
single_pred = best_model.predict([[6488, 2, 2, 9567, 1]])
print("\nSingle Sample Prediction (using best_model on train):", single_pred)

# ============================================
# 6. Retrain final model on ALL data using best params
#    (Used for production deployment / predicting new files)
# ============================================
best_params = grid_search.best_params_

final_model = Pipeline([
    ("scaler", StandardScaler()),
    ("model", LinearRegression())
])
final_model.set_params(**best_params)
final_model.fit(X, y)

print("\nFinal Linear Regression model (with standardization) trained on ALL data with best params:",
      best_params)

# Single sample prediction example (using the final model)
final_single_pred = final_model.predict([[6488, 2, 2, 9567, 1]])
print("Single Sample Prediction (final_model on ALL data):", final_single_pred)

# ============================================
# 7. Use final_model to predict a new file and save output
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

# 6. Save as a new "XXX.xlsx" (overwrite the original file)
output_file = 'output.xlsx'
new_df.to_excel(output_file, index=False)

print("\nPrediction completed with final standardized Linear Regression model. The file has been updated:",
      output_file)

# ============================================
# 8. Save hyperparameter tuning results to JSON
# ============================================
import json

json_file = "Linear_Regression_Hyperparameter_Tuning_Params.json"

with open(json_file, "w", encoding="utf-8") as f:
    json.dump(best_params, f, indent=4)

print(f"\nHyperparameter tuning results have been saved to: {json_file}")

# ============================================
# 9. Compute and display p-values using statsmodels
# ============================================
"""
sklearn's LinearRegression does not provide p-values.
To obtain p-values, we fit a separate OLS model using statsmodels.
This is for statistical inference (significance test), not for prediction.
"""

import statsmodels.api as sm

# Decide whether to include intercept according to best_params
fit_intercept = best_params.get("model__fit_intercept", True)

# Use the full dataset X, y for OLS
X_sm = X.copy()

if fit_intercept:
    # Add a constant term for the intercept
    X_sm = sm.add_constant(X_sm)

# Fit OLS model
ols_model = sm.OLS(y, X_sm).fit()

print("\n=== OLS Regression Results (statsmodels) ===")
print(ols_model.summary())

# If you want a clean table of coefficients and p-values:
coef_pvalues = pd.DataFrame({
    "coef": ols_model.params,
    "p_value": ols_model.pvalues
})

print("\n=== Coefficients and p-values ===")
print(coef_pvalues)