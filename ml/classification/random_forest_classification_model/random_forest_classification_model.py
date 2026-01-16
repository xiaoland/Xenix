# -*- coding: utf-8 -*-
"""
Random Forest Classification Model with Hyperparameter Tuning
for Stock Customer Churn

Notes:
- Random Forest is a tree-based model and is generally not sensitive to feature scaling.
  Therefore, we do NOT apply normalization here, in order to keep the data in its original scale.
- This script is written to be consistent in style with previous models
  (Logistic Regression, Decision Tree, Naive Bayes, KNN).

Steps:
1. (Check if normalization is necessary) For Random Forest, we skip normalization.
2. Tune key hyperparameters of Random Forest using GridSearchCV.
3. Save best-tuned parameters to a JSON file (Random_Forest_Classification_Model_Params.json).
4. Evaluate the tuned model (Accuracy, Precision, Recall, F1 Score, AUC Value)
   with robust handling for binary / multi-class / missing classes in test set.
5. Use the tuned model to predict for a single sample (generic for binary or multi-class).
6. Use the tuned model to predict for an input Excel file and save to output.xlsx
   (generic for binary or multi-class).
7. Use feature_importances_ (tree-based importance) and sort from high to low.
8. Ignore all warnings.
"""

import warnings
warnings.filterwarnings("ignore")  # Ignore all warnings

import json
import numpy as np
import pandas as pd

from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.ensemble import RandomForestClassifier
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
# Read the training data file; make sure the file is in the same directory
input_file = "Stock Customer Churn.xlsx"
df = pd.read_excel(input_file)

# Separate feature variables (X) and target variable (y)
# "Customer Churn (Yes/No)" is the target column, the rest are feature columns
X = df.drop(columns="Customer Churn (Yes/No)")
y = df["Customer Churn (Yes/No)"]

# Save the feature column names for later use (e.g., file prediction and feature importance)
feature_cols = X.columns.tolist()

# ==========================
# 2. Train-test split (no normalization for Random Forest)
# ==========================
# Split data into training and test sets
# test_size=0.2 means 20% of data used as test set
# random_state=0 for reproducible splitting
# stratify=y keeps the class distribution similar in train and test sets
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=0,
    stratify=y
)

# NOTE:
# Random Forest is a tree-based model and is not sensitive to feature scaling.
# Therefore, we do NOT perform normalization here to keep the original feature scale.

# ==========================
# 3. Hyperparameter tuning for Random Forest
# ==========================
# Create a base Random Forest model
base_model = RandomForestClassifier(random_state=0)

# Define the parameter grid for tuning (concise, common values)
param_grid = {
    "n_estimators": [100, 200, 300],   # Number of trees in the forest
    "max_depth": [None, 5, 10, 15],   # Maximum depth of each tree
    # You can uncomment more parameters if you want a larger search:
    # "min_samples_split": [2, 5, 10],
    # "min_samples_leaf": [1, 2, 4],
    # "max_features": ["sqrt", "log2", None],
    # "bootstrap": [True, False],
    # "class_weight": [None, "balanced"]
}

# Set up GridSearchCV for hyperparameter tuning
# scoring="f1_weighted" works for both binary and multi-class classification
grid_search = GridSearchCV(
    estimator=base_model,
    param_grid=param_grid,
    scoring="f1_weighted",
    cv=5,
    n_jobs=-1,
    verbose=0
)

# Fit the grid search on the training data (no scaling)
grid_search.fit(X_train, y_train)

# Get the best model and best parameters
best_model = grid_search.best_estimator_
best_params = grid_search.best_params_

# ==========================
# 4. Save tuned parameters to JSON file
# ==========================
# Only save the tuned parameters, no other information
# File name is Random_Forest_Classification_Model_Params.json
params_filename = "Random_Forest_Classification_Model_Params.json"
with open(params_filename, "w", encoding="utf-8") as f:
    json.dump(best_params, f, indent=4)

print("Best tuned parameters:")
print(best_params)
print(f"Tuned parameters saved to: {params_filename}")

# ==========================
# 5. Model evaluation on test set (robust AUC)
# ==========================
# Predict class labels on the test set
y_pred = best_model.predict(X_test)

# Predict class probabilities on the test set (for AUC and other analysis)
y_proba = best_model.predict_proba(X_test)

# Classes learned by the model
classes_model = list(best_model.classes_)
n_classes_model = len(classes_model)

# Number of unique classes in the training data (global classification type)
true_classes = np.unique(y_train)
n_true_classes = len(true_classes)

# Compute Accuracy (works for any number of classes)
accuracy = accuracy_score(y_test, y_pred)

# -------- Binary vs multi-class handling with robust AUC --------
if n_true_classes == 2:
    # ===== Global binary classification =====
    precision = precision_score(y_test, y_pred, zero_division=0)
    recall = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)

    # If the test set contains only 1 class, AUC is undefined
    test_labels = np.unique(y_test)
    if len(test_labels) < 2:
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
        # Only one class present in test set -> AUC is undefined
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

print("\nEvaluation metrics on test set (with tuned parameters):")
print(f"Accuracy : {accuracy:.4f}")
print(f"Precision: {precision:.4f}")
print(f"Recall   : {recall:.4f}")
print(f"F1 Score : {f1:.4f}")
print(f"AUC Value: {auc_value:.4f}")

# ==========================
# 6. Single sample prediction (generic multi-class)
# ==========================
# Single sample feature values
# NOTE: The length of this list must match the number of features.
#       The order of values must be the same as feature_cols.
single_sample = [22686.5, 297, 149.25, 2029.85, 0]

# Convert to 2D array with shape (1, n_features)
single_sample_array = np.array(single_sample).reshape(1, -1)

# Predict class for the single sample
single_pred_class = best_model.predict(single_sample_array)[0]

# Predict probabilities for all classes
single_pred_proba = best_model.predict_proba(single_sample_array)[0]  # shape: (n_classes,)

print("\nSingle sample prediction:")
print("Input features:", single_sample)
print("Predicted class:", single_pred_class)
print("Class probabilities:")
for idx, cls in enumerate(classes_model):
    print(f"  Class {cls}: {single_pred_proba[idx]:.4f}")

# ==========================
# 7. File prediction (generic multi-class)
# ==========================
# Input file for prediction; all columns in this file are features
pre_file = "Stock Customer Churn - test.xlsx"

# Read the new data file
df_new = pd.read_excel(pre_file)

# Ensure the feature columns match those used in training
# This assumes df_new contains the same feature columns in any order
X_new = df_new[feature_cols]

# Predict class labels for the new data
y_new_pred = best_model.predict(X_new)

# Predict class probabilities for the new data
y_new_proba = best_model.predict_proba(X_new)  # shape: (n_samples, n_classes)

# Add predicted class labels to the new dataframe
df_new["Predicted Class"] = y_new_pred

# Add probability columns for each class
for idx, cls in enumerate(classes_model):
    col_name = f"Probability of {cls}"
    df_new[col_name] = y_new_proba[:, idx]

# Save the results to output.xlsx
output_file = "output.xlsx"
df_new.to_excel(output_file, index=False)

print(f"\nFile prediction completed. Saved to \"{output_file}\".")

# ==========================
# 8. Feature importance
# ==========================
print("\nFeature importance (sorted from high to low):")

if hasattr(best_model, "feature_importances_"):
    # Random Forest provides feature_importances_ (Gini importance)
    print("Using model.feature_importances_ from Random Forest as feature importance.")
    importance = best_model.feature_importances_
else:
    # Fallback case: if no feature_importances_ exists (should not happen for RandomForest)
    print("Model does NOT have 'feature_importances_'. Using zeros as placeholder.")
    importance = np.zeros(len(feature_cols))

# Create a DataFrame of feature importance
importance_df = pd.DataFrame({
    "Feature": feature_cols,
    "Importance": importance
})

# Sort by importance from high to low
importance_df = importance_df.sort_values(by="Importance", ascending=False).reset_index(drop=True)

print(importance_df)
