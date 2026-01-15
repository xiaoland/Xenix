# -*- coding: utf-8 -*-
"""
LightGBM Classification Model (LGBMClassifier) with Hyperparameter Tuning
for Stock Customer Churn

Notes:
- LightGBM is a tree-based gradient boosting model and is not very sensitive to
  feature scaling. Therefore, we DO NOT apply normalization here.
- We dynamically choose the objective:
    * if number of classes == 2  -> 'binary'
    * if number of classes > 2   -> 'multiclass' + num_class
- Parameter grid style is consistent with previous models.
- verbose=-1 and verbosity=-1 are used to silence LightGBM internal logs.

Steps:
1. No normalization (tree-based model).
2. Hyperparameter tuning with GridSearchCV.
3. Save best parameters into JSON (LightGBM_Classification_Model_Params.json).
4. Evaluate the model (Accuracy, Precision, Recall, F1 Score, AUC).
5. Single-sample prediction (multi-class compatible).
6. Excel file prediction and output to output.xlsx.
7. Feature importance via feature_importances_ (or alternative if not available).
8. Ignore warnings.
"""

import warnings
warnings.filterwarnings("ignore")  # Ignore all Python warnings

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

from lightgbm import LGBMClassifier

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

# Number of unique classes in the whole dataset (for objective)
n_classes = y.nunique()
print(f"Detected number of classes in target: {n_classes}")

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
# LightGBM is tree-based and generally not sensitive to feature scaling.
# Therefore, we do NOT apply normalization here.

# ==========================
# 3. Hyperparameter tuning for LightGBM
# ==========================

# Dynamically choose objective and num_class based on number of classes
if n_classes == 2:
    # Binary classification
    lgbm_objective = "binary"
    base_model = LGBMClassifier(
        objective=lgbm_objective,
        random_state=0,
        n_jobs=-1,
        verbose=-1,     # silence LightGBM logs
        verbosity=-1
    )
else:
    # Multi-class classification
    lgbm_objective = "multiclass"
    base_model = LGBMClassifier(
        objective=lgbm_objective,
        num_class=n_classes,  # MUST be specified for multiclass
        random_state=0,
        n_jobs=-1,
        verbose=-1,
        verbosity=-1
    )

print(f"Using LightGBM objective: {lgbm_objective}")

# Parameter grid (simplified to speed up search)
param_grid = {
    "n_estimators": [100, 200],   # Number of boosting iterations
    "max_depth": [-1, 5, 10],     # -1 means no limit
    # You can uncomment more params if you want a larger search:
    # "learning_rate": [0.05, 0.1],
    # "num_leaves": [31, 63],
    # "min_child_samples": [20, 40],
    # "subsample": [0.8, 1.0],
    # "colsample_bytree": [0.8, 1.0],
    # "reg_lambda": [0.0, 1.0]
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
json_filename = "LightGBM_Classification_Model_Params.json"
with open(json_filename, "w", encoding="utf-8") as f:
    json.dump(best_params, f, indent=4)

print("Best tuned parameters:")
print(best_params)
print(f"Tuned parameters saved to: {json_filename}")

# ==========================
# 5. Evaluation on test set (robust AUC for binary & multiclass)
# ==========================
# Predict labels
y_pred = best_model.predict(X_test)

# Predict probabilities
y_proba = best_model.predict_proba(X_test)

# Decide if the true problem is binary or multi-class based on TRAINING set
true_classes = np.unique(y_train)
n_true_classes = len(true_classes)

# Accuracy
accuracy = accuracy_score(y_test, y_pred)

if n_true_classes == 2:
    # ------- TRUE BINARY CLASSIFICATION -------
    precision = precision_score(y_test, y_pred, zero_division=0)
    recall = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)

    # Positive class is the greater label in true_classes
    pos_class = sorted(true_classes)[1]
    pos_index = list(best_model.classes_).index(pos_class)
    auc_value = roc_auc_score(y_test, y_proba[:, pos_index])

else:
    # ------- TRUE MULTI-CLASS CLASSIFICATION -------
    precision = precision_score(y_test, y_pred, average="weighted", zero_division=0)
    recall = recall_score(y_test, y_pred, average="weighted", zero_division=0)
    f1 = f1_score(y_test, y_pred, average="weighted", zero_division=0)

    # Labels actually present in THIS test set
    test_labels = np.unique(y_test)

    if len(test_labels) <= 1:
        # Cannot compute AUC when only one class appears in y_test
        auc_value = float("nan")
    elif len(test_labels) == 2:
        # Although the global task is multi-class, this test set behaves like binary.
        # So we compute a binary ROC AUC on the two present labels.
        pos_class = sorted(test_labels)[1]
        pos_index = list(best_model.classes_).index(pos_class)
        auc_value = roc_auc_score(y_test, y_proba[:, pos_index])
    else:
        # Real multi-class AUC (OvR) on 3 or more labels
        classes_model = list(best_model.classes_)
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
for idx, cls in enumerate(best_model.classes_):
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

for idx, cls in enumerate(best_model.classes_):
    df_new[f"Probability of {cls}"] = y_new_proba[:, idx]

output_file = "output.xlsx"
df_new.to_excel(output_file, index=False)

print(f"\nFile prediction completed. Saved to \"{output_file}\".")

# ==========================
# 8. Feature importance
# ==========================
print("\nFeature importance (sorted from high to low):")

if hasattr(best_model, "feature_importances_"):
    # LightGBM provides feature_importances_
    print("Using model.feature_importances_ from LightGBM.")
    importance = best_model.feature_importances_
else:
    # Fallback: permutation importance
    print("Model does NOT have 'feature_importances_'. Using permutation importance instead.")
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
