# -*- coding: utf-8 -*-
"""
K-Nearest Neighbors Classification Model with Normalization and Hyperparameter Tuning
for Stock Customer Churn

Steps:
1. Normalize feature data (Z-score normalization) based on training set.
2. Tune key hyperparameters of KNN using GridSearchCV.
3. Save best-tuned parameters to a JSON file (K-Nearest_Neighbors_Classification_Model_Params.json).
4. Evaluate the tuned model (Accuracy, Precision, Recall, F1 Score, AUC Value).
5. Use the tuned model to predict for a single sample (generic for binary or multi-class).
6. Use the tuned model to predict for an input Excel file and save to output.xlsx
   (generic for binary or multi-class).
7. If the model has feature_importances_, display feature importance sorted from high to low.
   If not, use another method (permutation importance) and clearly indicate it.
8. Ignore all warnings.
"""

import warnings
warnings.filterwarnings("ignore")  # Ignore all warnings

import json
import numpy as np
import pandas as pd

from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.preprocessing import StandardScaler  # For Z-score normalization
from sklearn.neighbors import KNeighborsClassifier
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score
)
from sklearn.inspection import permutation_importance  # For alternative feature importance

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
# 2. Split data, then normalize (Z-score)
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

# Create a StandardScaler object for Z-score normalization
# Z-score normalization rescales data to have mean 0 and standard deviation 1
scaler = StandardScaler()

# Fit the scaler on training feature data and transform both train and test
# KNN is distance-based, so normalization is very important for this model
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

# ==========================
# 3. Hyperparameter tuning for KNN
# ==========================
# Create a base KNeighborsClassifier model
base_model = KNeighborsClassifier()

# Define the parameter grid for tuning
# These are common and important hyperparameters for KNN
param_grid = {
    "n_neighbors": [3, 5, 7, 9, 11],       # Number of neighbors
    "weights": ["uniform", "distance"],    # Uniform or distance-based weighting
    "metric": ["euclidean", "manhattan", "minkowski"],  # Distance metric
    "p": [1, 2]                            # Power parameter for Minkowski (1=Manhattan, 2=Euclidean)
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

# Fit the grid search on the normalized training data
grid_search.fit(X_train_scaled, y_train)

# Get the best model and best parameters
best_model = grid_search.best_estimator_
best_params = grid_search.best_params_

# ==========================
# 4. Save tuned parameters to JSON file
# ==========================
# Only save the tuned parameters, no other information
# File name is K-Nearest_Neighbors_Classification_Model_Params.json
params_filename = "K-Nearest_Neighbors_Classification_Model_Params.json"
with open(params_filename, "w", encoding="utf-8") as f:
    json.dump(best_params, f, indent=4)

print("Best tuned parameters:")
print(best_params)
print(f"Tuned parameters saved to: {params_filename}")

# ==========================
# 5. Model evaluation on test set (robust AUC for binary & multiclass)
# ==========================
# Predict class labels on the test set
y_pred = best_model.predict(X_test_scaled)

# Predict class probabilities on the test set
# This is needed for AUC and for probability-based evaluation
y_proba = best_model.predict_proba(X_test_scaled)

# Decide if the true problem is binary or multi-class based on TRAINING set
true_classes = np.unique(y_train)
n_true_classes = len(true_classes)

# Compute Accuracy (works for any number of classes)
accuracy = accuracy_score(y_test, y_pred)

if n_true_classes == 2:
    # ------- TRUE BINARY CLASSIFICATION -------
    precision = precision_score(y_test, y_pred, zero_division=0)
    recall = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)

    # For AUC in binary case, use probability of the positive class
    # The positive class is taken as the larger label in training set
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
        # Only one class in y_test -> AUC is undefined
        auc_value = float("nan")
    elif len(test_labels) == 2:
        # This particular test behaves like binary (two classes only)
        pos_class = sorted(test_labels)[1]
        pos_index = list(best_model.classes_).index(pos_class)
        auc_value = roc_auc_score(y_test, y_proba[:, pos_index])
    else:
        # Real multi-class case (>= 3 labels in test set)
        classes_model = list(best_model.classes_)
        # Align probability columns with labels in y_test
        col_indices = [classes_model.index(lbl) for lbl in test_labels]
        y_proba_aligned = y_proba[:, col_indices]

        auc_value = roc_auc_score(
            y_test,
            y_proba_aligned,
            multi_class="ovr",
            average="weighted"
        )

# Print evaluation metrics
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

# Apply the same scaler used for training to the single sample
single_sample_scaled = scaler.transform(single_sample_array)

# Predict class for the single sample
single_pred_class = best_model.predict(single_sample_scaled)[0]

# Predict probabilities for all classes
single_pred_proba = best_model.predict_proba(single_sample_scaled)[0]  # shape: (n_classes,)

print("\nSingle sample prediction:")
print("Input features:", single_sample)
print("Predicted class:", single_pred_class)

print("Class probabilities:")
for idx, cls in enumerate(best_model.classes_):
    print(f"  Class {cls}: {single_pred_proba[idx]:.4f}")

# ==========================
# 7. File prediction (generic multi-class)
# ==========================
# Input file for prediction; all columns in this file are features
pre_file = "Stock Customer Churn - test.xlsx"
df_new = pd.read_excel(pre_file)

# Read the new data file
df_new = pd.read_excel(pre_file)

# Ensure the feature columns match those used in training
# This assumes df_new contains the same feature columns in any order
X_new = df_new[feature_cols]

# Apply the same scaler to the new feature data
X_new_scaled = scaler.transform(X_new)

# Predict class labels for the new data
y_new_pred = best_model.predict(X_new_scaled)

# Predict class probabilities for the new data
y_new_proba = best_model.predict_proba(X_new_scaled)  # shape: (n_samples, n_classes)

# Add predicted class labels to the new dataframe
df_new["Predicted Class"] = y_new_pred

# Add probability columns for each class
for idx, cls in enumerate(best_model.classes_):
    # Column name example: "Probability of 0", "Probability of 1", or "Probability of Yes", etc.
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
    # KNN normally does NOT have feature_importances_,
    # but we keep this branch for API completeness.
    print("Using model.feature_importances_ as feature importance.")
    importance = best_model.feature_importances_
else:
    # KNN does not provide built-in feature_importances_
    # We use permutation importance as an alternative method
    # and clearly indicate this is not an internal importance measure.
    print("Model does NOT have 'feature_importances_'.")
    print("Using permutation importance as an alternative feature importance method.")
    # Compute permutation importance on the test set
    # Here we use 'f1_weighted' as the scoring metric
    perm_result = permutation_importance(
        best_model,
        X_test_scaled,
        y_test,
        scoring="f1_weighted",
        n_repeats=10,
        random_state=0,
        n_jobs=-1
    )
    # The importances_mean attribute gives the average importance over permutations
    importance = perm_result.importances_mean  # shape: (n_features,)

# Create a DataFrame of feature importance
importance_df = pd.DataFrame({
    "Feature": feature_cols,
    "Importance": importance
})

# Sort by importance from high to low
importance_df = importance_df.sort_values(by="Importance", ascending=False).reset_index(drop=True)

print(importance_df)
