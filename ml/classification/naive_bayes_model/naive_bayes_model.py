# -*- coding: utf-8 -*-
"""
Naive Bayes Model (GaussianNB) with Normalization and Hyperparameter Tuning
for Stock Customer Churn

Notes:
- We use GaussianNB for continuous numeric features.
- We APPLY Z-score normalization (mean=0, std=1) before training and prediction.
- Parameter grid style is consistent with other models (concise and common values).

Steps:
1. Normalize feature data (Z-score) based on training set.
2. Tune key hyperparameters of GaussianNB using GridSearchCV.
3. Save best-tuned parameters to a JSON file (Naive_Bayes_Model_Params.json).
4. Evaluate the tuned model (Accuracy, Precision, Recall, F1 Score, AUC Value).
5. Predict for a single sample (generic for binary or multi-class).
6. Predict for an input Excel file and save results to output.xlsx.
7. If feature_importances_ exists, use it; otherwise, use an alternative
   importance based on class-conditional means (theta_) and clearly indicate this.
8. Ignore all warnings.
"""

import warnings
warnings.filterwarnings("ignore")  # Ignore all warnings

import json
import numpy as np
import pandas as pd

from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.preprocessing import StandardScaler
from sklearn.naive_bayes import GaussianNB
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score
)

# ==========================
# 1. Read data
# ==========================
# Make sure the Excel file is in the same directory as this script
input_file = "Stock Customer Churn.xlsx"
df = pd.read_excel(input_file)

# X = all feature columns; y = target column
X = df.drop(columns="Customer Churn (Yes/No)")
y = df["Customer Churn (Yes/No)"]

# Save feature column names for later usage (prediction and feature importance)
feature_cols = X.columns.tolist()

# ==========================
# 2. Train-test split + normalization
# ==========================
# Split into training and test sets
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=0,
    stratify=y  # keep class distribution similar
)

# Create a StandardScaler for Z-score normalization
scaler = StandardScaler()

# Fit on training data and transform both training and test data
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

# ==========================
# 3. Hyperparameter tuning for GaussianNB
# ==========================
# Base Gaussian Naive Bayes model
base_model = GaussianNB()

# Parameter grid:
# var_smoothing is a small value added to variances for numerical stability
param_grid = {
    "var_smoothing": np.logspace(-12, -6, 7)  # 1e-12, 1e-11, ..., 1e-6
}

# Set up GridSearchCV
grid_search = GridSearchCV(
    estimator=base_model,
    param_grid=param_grid,
    scoring="f1_weighted",
    cv=5,
    n_jobs=-1,
    verbose=0
)

# Fit the grid search on the scaled training data
grid_search.fit(X_train_scaled, y_train)

# Get best model and parameters
best_model = grid_search.best_estimator_
best_params = grid_search.best_params_

# ==========================
# 4. Save tuned parameters to JSON
# ==========================
json_filename = "Naive_Bayes_Model_Params.json"
with open(json_filename, "w", encoding="utf-8") as f:
    json.dump(best_params, f, indent=4)

print("Best tuned parameters:")
print(best_params)
print(f"Tuned parameters saved to: {json_filename}")

# ==========================
# 5. Evaluation on test set (robust multi-class AUC)
# ==========================
# Predict labels
y_pred = best_model.predict(X_test_scaled)

# Predict probabilities (for AUC and probability-based analysis)
y_proba = best_model.predict_proba(X_test_scaled)

# Classes learned by the model
classes_model = list(best_model.classes_)
n_classes_model = len(classes_model)

# Determine how many classes exist in the whole training set
true_classes = np.unique(y_train)
n_true_classes = len(true_classes)

# Accuracy
accuracy = accuracy_score(y_test, y_pred)

# Precision, Recall, F1, AUC (robust to missing classes in test set)
if n_true_classes == 2:
    # ===== Binary classification (global) =====
    precision = precision_score(y_test, y_pred, zero_division=0)
    recall = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)

    # If the test set contains only 1 class, AUC is undefined
    test_labels = np.unique(y_test)
    if len(test_labels) < 2:
        auc_value = float("nan")
    else:
        # Positive class is the larger label
        pos_class = sorted(test_labels)[1]
        pos_index = classes_model.index(pos_class)
        auc_value = roc_auc_score(y_test, y_proba[:, pos_index])

else:
    # ===== Multi-class classification (global) =====
    precision = precision_score(y_test, y_pred, average="weighted", zero_division=0)
    recall = recall_score(y_test, y_pred, average="weighted", zero_division=0)
    f1 = f1_score(y_test, y_pred, average="weighted", zero_division=0)

    test_labels = np.unique(y_test)

    if len(test_labels) <= 1:
        # Only one class in test set -> AUC is undefined
        auc_value = float("nan")
    elif len(test_labels) == 2:
        # Test set effectively behaves like binary classification
        pos_class = sorted(test_labels)[1]
        pos_index = classes_model.index(pos_class)
        auc_value = roc_auc_score(y_test, y_proba[:, pos_index])
    else:
        # True multi-class AUC: align probability columns with labels in test set
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
# NOTE: Order must match feature_cols and length = number of features
single_sample = [22686.5, 297, 149.25, 2029.85, 0]

# Convert to 2D array
single_array = np.array(single_sample).reshape(1, -1)

# Apply the same scaler
single_scaled = scaler.transform(single_array)

# Predict class and probabilities
single_pred_class = best_model.predict(single_scaled)[0]
single_pred_proba = best_model.predict_proba(single_scaled)[0]

print("\nSingle sample prediction:")
print("Input features:", single_sample)
print("Predicted class:", single_pred_class)
print("Class probabilities:")
for idx, cls in enumerate(best_model.classes_):
    print(f"  Class {cls}: {single_pred_proba[idx]:.4f}")

# ==========================
# 7. File prediction (generic multi-class)
# ==========================
# Read new data file; all columns in this file are features
pre_file = "Stock Customer Churn - test.xlsx"
df_new = pd.read_excel(pre_file)

# Ensure the feature columns align with training features
X_new = df_new[feature_cols]

# Scale new data using the same scaler
X_new_scaled = scaler.transform(X_new)

# Predict labels and probabilities
y_new_pred = best_model.predict(X_new_scaled)
y_new_proba = best_model.predict_proba(X_new_scaled)

# Add predictions to dataframe
df_new["Predicted Class"] = y_new_pred

# Add probability columns for each class
for idx, cls in enumerate(best_model.classes_):
    df_new[f"Probability of {cls}"] = y_new_proba[:, idx]

# Save to output.xlsx
output_file = "output.xlsx"
df_new.to_excel(output_file, index=False)

print(f"\nFile prediction completed. Saved to \"{output_file}\".")

# ==========================
# 8. Feature importance (alternative method)
# ==========================
print("\nFeature importance (sorted from high to low):")

if hasattr(best_model, "feature_importances_"):
    # GaussianNB normally does NOT provide feature_importances_,
    # but we keep this branch for completeness.
    print("Using model.feature_importances_ as feature importance.")
    importance = best_model.feature_importances_
else:
    # GaussianNB does not provide feature_importances_.
    # We use an alternative proxy based on class-conditional means (theta_).
    print("Model does NOT have 'feature_importances_'.")
    print("Using alternative importance based on class-conditional means (theta_).")

    # theta_ has shape (n_classes, n_features): mean of each feature per class
    theta = best_model.theta_

    # Compute overall mean per feature across classes
    overall_mean = np.mean(theta, axis=0)  # shape: (n_features,)

    # Define importance as average absolute deviation from overall mean across classes
    importance = np.mean(np.abs(theta - overall_mean), axis=0)  # shape: (n_features,)

# Create importance DataFrame
importance_df = pd.DataFrame({
    "Feature": feature_cols,
    "Importance": importance
}).sort_values(by="Importance", ascending=False).reset_index(drop=True)

print(importance_df)
