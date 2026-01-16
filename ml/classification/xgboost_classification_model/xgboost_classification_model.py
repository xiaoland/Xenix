# -*- coding: utf-8 -*-
"""
XGBoost Classification Model with Hyperparameter Tuning
for Stock Customer Churn

Notes:
- XGBoost is a tree-based gradient boosting model and is not very sensitive
  to feature scaling. Therefore, we DO NOT apply normalization here.
- We use the sklearn-compatible XGBClassifier wrapper.
- Parameter grid style is consistent with previous models (concise, common values).

Steps:
1. No normalization (tree-based model).
2. Hyperparameter tuning with GridSearchCV.
3. Save best parameters into JSON (XGBoost_Classification_Model_Params.json).
4. Evaluate the model (Accuracy, Precision, Recall, F1 Score, AUC) with robust
   handling for binary / multi-class / missing classes in the test set.
5. Single-sample prediction (multi-class compatible).
6. Excel file prediction and output to output.xlsx.
7. Feature importance via feature_importances_ (or permutation importance if not available).
8. Ignore warnings.
"""

import warnings
warnings.filterwarnings("ignore")  # Ignore all warnings

import json
import numpy as np
import pandas as pd

from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score
)
from sklearn.inspection import permutation_importance

from xgboost import XGBClassifier

# ==========================
# 1. Read data
# ==========================
# Make sure the Excel file is in the same directory as this script
input_file = "Stock Customer Churn.xlsx"
df = pd.read_excel(input_file)

# X = all feature columns; y = target column
X = df.drop(columns="Customer Churn (Yes/No)")
y = df["Customer Churn (Yes/No)"]

# Save feature column names for later usage (file prediction / feature importance)
feature_cols = X.columns.tolist()

# ==========================
# 2. Train-test split (no normalization)
# ==========================
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=0,
    stratify=y  # keep class distribution similar
)

# NOTE:
# XGBoost (tree-based) is generally not sensitive to feature scaling.
# Therefore, we do NOT apply normalization here.

# ==========================
# 3. Hyperparameter tuning for XGBoost
# ==========================
# Base XGBoost model
base_model = XGBClassifier(
    use_label_encoder=False,  # avoid label encoder warning in older versions
    eval_metric="logloss",    # default evaluation metric
    random_state=0,
    n_jobs=-1                 # use all CPU cores
)

# Parameter grid (common, practical values)
param_grid = {
    "n_estimators": [100, 200],          # Number of trees
    "learning_rate": [0.05, 0.1],        # Step size shrinkage
    "max_depth": [3, 5],                 # Depth of trees
    "min_child_weight": [1, 3],          # Min sum of instance weight (hessian) in a child
    "subsample": [0.8, 1.0],             # Row sampling
    "colsample_bytree": [0.8, 1.0],      # Column sampling
    "reg_lambda": [1.0, 2.0]             # L2 regularization term on weights
}

grid_search = GridSearchCV(
    estimator=base_model,
    param_grid=param_grid,
    scoring="f1_weighted",
    cv=5,
    n_jobs=-1,
    verbose=0
)

# Fit grid search
grid_search.fit(X_train, y_train)

# Best model and best parameters
best_model = grid_search.best_estimator_
best_params = grid_search.best_params_

# ==========================
# 4. Save tuned parameters to JSON
# ==========================
json_filename = "XGBoost_Classification_Model_Params.json"
with open(json_filename, "w", encoding="utf-8") as f:
    json.dump(best_params, f, indent=4)

print("Best tuned parameters:")
print(best_params)
print(f"Tuned parameters saved to: {json_filename}")

# ==========================
# 5. Evaluation on test set (robust AUC)
# ==========================
# Predict labels
y_pred = best_model.predict(X_test)

# Predict probabilities
y_proba = best_model.predict_proba(X_test)

# Classes known by the model
classes_model = list(best_model.classes_)
n_classes_model = len(classes_model)

# Determine global classification type based on training labels
true_classes = np.unique(y_train)
n_true_classes = len(true_classes)

# Accuracy
accuracy = accuracy_score(y_test, y_pred)

# -------- Binary vs multi-class handling with robust AUC --------
if n_true_classes == 2:
    # ===== Global binary classification =====
    precision = precision_score(y_test, y_pred, zero_division=0)
    recall = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)

    # Unique labels actually present in the test set
    test_labels = np.unique(y_test)

    if len(test_labels) < 2:
        # Only one class present in the test set -> AUC is undefined
        auc_value = float("nan")
    else:
        # Choose the larger label in the test set as the positive class
        pos_class = sorted(test_labels)[1]
        pos_index = classes_model.index(pos_class)
        auc_value = roc_auc_score(y_test, y_proba[:, pos_index])

else:
    # ===== Global multi-class classification =====
    precision = precision_score(y_test, y_pred, average="weighted", zero_division=0)
    recall = recall_score(y_test, y_pred, average="weighted", zero_division=0)
    f1 = f1_score(y_test, y_pred, average="weighted", zero_division=0)

    # Unique labels actually present in the test set
    test_labels = np.unique(y_test)

    if len(test_labels) <= 1:
        # Only one class present in the test set -> AUC is undefined
        auc_value = float("nan")
    elif len(test_labels) == 2:
        # Test set behaves like binary classification
        pos_class = sorted(test_labels)[1]
        pos_index = classes_model.index(pos_class)
        auc_value = roc_auc_score(y_test, y_proba[:, pos_index])
    else:
        # True multi-class AUC: align probability columns with test labels
        col_indices = [classes_model.index(lbl) for lbl in test_labels]
        y_proba_aligned = y_proba[:, col_indices]

        auc_value = roc_auc_score(
            y_test,
            y_proba_aligned,
            multi_class="ovr",
            average="weighted"
        )

print("\nEvaluation metrics on test set:")
print(f"Accuracy : {accuracy:.4f}")
print(f"Precision: {precision:.4f}")
print(f"Recall   : {recall:.4f}")
print(f"F1 Score : {f1:.4f}")
print(f"AUC Value: {auc_value:.4f}")

# ==========================
# 6. Single sample prediction (generic multi-class)
# ==========================
# Single sample feature values
# NOTE: The order must match feature_cols and length must equal number of features.
single_sample = [22686.5, 297, 149.25, 2029.85, 0]

single_array = np.array(single_sample).reshape(1, -1)

single_pred_class = best_model.predict(single_array)[0]
single_pred_proba = best_model.predict_proba(single_array)[0]

print("\nSingle sample prediction:")
print("Input features:", single_sample)
print("Predicted class:", single_pred_class)
print("Class probabilities:")
for idx, cls in enumerate(classes_model):
    print(f"  Class {cls}: {single_pred_proba[idx]:.4f}")

# ==========================
# 7. File prediction (generic multi-class)
# ==========================
pre_file = "Stock Customer Churn - test.xlsx"
df_new = pd.read_excel(pre_file)

# Ensure feature columns align with training set
X_new = df_new[feature_cols]

# Predict labels and probabilities
y_new_pred = best_model.predict(X_new)
y_new_proba = best_model.predict_proba(X_new)

# Add predictions to dataframe
df_new["Predicted Class"] = y_new_pred

for idx, cls in enumerate(classes_model):
    df_new[f"Probability of {cls}"] = y_new_proba[:, idx]

output_file = "output.xlsx"
df_new.to_excel(output_file, index=False)

print(f"\nFile prediction completed. Saved to \"{output_file}\".")

# ==========================
# 8. Feature importance
# ==========================
print("\nFeature importance (sorted from high to low):")

if hasattr(best_model, "feature_importances_"):
    # XGBoost provides feature_importances_
    print("Using model.feature_importances_ from XGBoost.")
    importance = best_model.feature_importances_
else:
    # Fallback: permutation importance
    print("Model does NOT have 'feature_importances_'.")
    print("Using permutation importance as an alternative method.")
    perm = permutation_importance(
        best_model,
        X_test,
        y_test,
        scoring="f1_weighted",
        n_repeats=10,
        random_state=0,
        n_jobs=-1
    )
    importance = perm.importances_mean

importance_df = pd.DataFrame({
    "Feature": feature_cols,
    "Importance": importance
}).sort_values(by="Importance", ascending=False).reset_index(drop=True)

print(importance_df)
