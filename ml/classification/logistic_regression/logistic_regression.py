# -*- coding: utf-8 -*-
"""
Logistic Regression with Normalization and Hyperparameter Tuning
for Stock Customer Churn

Steps:
1. Normalize feature data (Z-score normalization) based on training set.
2. Tune key hyperparameters of Logistic Regression using GridSearchCV.
3. Save tuned parameters to JSON (Logistic_Regression_Params.json).
4. Evaluate the model (Accuracy, Precision, Recall, F1 Score, AUC Value).
5. Predict a single sample (binary or multi-class).
6. Predict an external Excel file and save output.xlsx (binary or multi-class).
7. Logistic Regression has no feature_importances_; use coefficient-based importance.
8. Suppress all warnings (including ConvergenceWarning).
"""

import warnings
warnings.filterwarnings("ignore")  # Suppress ALL warnings

import json
import numpy as np
import pandas as pd

from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score
)
from sklearn.exceptions import ConvergenceWarning

warnings.filterwarnings("ignore", category=ConvergenceWarning)  # Extra suppression


# ==========================
# 1. Read dataset
# ==========================
input_file = "Stock Customer Churn.xlsx"
df = pd.read_excel(input_file)

# X = features, y = target
X = df.drop(columns="Customer Churn (Yes/No)")
y = df["Customer Churn (Yes/No)"]

feature_cols = X.columns.tolist()


# ==========================
# 2. Train-test split + Z-score normalization
# ==========================
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=0,
    stratify=y
)

# Z-score normalization
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)


# ==========================
# 3. Hyperparameter tuning
# ==========================
base_model = LogisticRegression(random_state=0)

# Common hyperparameter grid (consistent style)
param_grid = {
    "C": [0.01, 0.1, 1, 10, 100],
    # "penalty": ["l1", "l2"],
    # "class_weight": [None, "balanced"],
    # "solver": ["liblinear"],        # supports l1 and l2
    "max_iter": [2000, 5000, 8000]     # increased to avoid convergence warnings
}

grid_search = GridSearchCV(
    estimator=base_model,
    param_grid=param_grid,
    scoring="f1_weighted",
    cv=5,
    n_jobs=-1,
    verbose=0
)

grid_search.fit(X_train_scaled, y_train)

best_model = grid_search.best_estimator_
best_params = grid_search.best_params_


# ==========================
# 4. Save tuned parameters to JSON
# ==========================
json_filename = "Logistic_Regression_Params.json"
with open(json_filename, "w", encoding="utf-8") as f:
    json.dump(best_params, f, indent=4)

print("Best tuned parameters:")
print(best_params)


# ==========================
# 5. Evaluation (Robust multi-class AUC)
# ==========================
y_pred = best_model.predict(X_test_scaled)
y_proba = best_model.predict_proba(X_test_scaled)

true_classes = np.unique(y_train)
n_true_classes = len(true_classes)

# Standard metrics
accuracy = accuracy_score(y_test, y_pred)

if n_true_classes == 2:
    # -------- Binary classification --------
    precision = precision_score(y_test, y_pred, zero_division=0)
    recall = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)

    # Use probability for the positive class
    pos_class = sorted(true_classes)[1]
    pos_index = list(best_model.classes_).index(pos_class)
    auc_value = roc_auc_score(y_test, y_proba[:, pos_index])

else:
    # -------- Multi-class classification --------
    precision = precision_score(y_test, y_pred, average="weighted", zero_division=0)
    recall = recall_score(y_test, y_pred, average="weighted", zero_division=0)
    f1 = f1_score(y_test, y_pred, average="weighted", zero_division=0)

    # Determine classes present in test set
    test_labels = np.unique(y_test)

    if len(test_labels) <= 1:
        auc_value = float("nan")  # AUC is undefined
    elif len(test_labels) == 2:
        # Test set is effectively binary
        pos_class = sorted(test_labels)[1]
        pos_index = list(best_model.classes_).index(pos_class)
        auc_value = roc_auc_score(y_test, y_proba[:, pos_index])
    else:
        # True multi-class AUC (One-vs-Rest)
        cls_model = list(best_model.classes_)
        col_idx = [cls_model.index(lbl) for lbl in test_labels]
        y_proba_aligned = y_proba[:, col_idx]

        auc_value = roc_auc_score(
            y_test,
            y_proba_aligned,
            multi_class="ovr",
            average="weighted"
        )

print("\nEvaluation metrics:")
print(f"Accuracy : {accuracy:.4f}")
print(f"Precision: {precision:.4f}")
print(f"Recall   : {recall:.4f}")
print(f"F1 Score : {f1:.4f}")
print(f"AUC Value: {auc_value:.4f}")


# ==========================
# 6. Single-Sample Prediction
# ==========================
single_sample = [22686.5, 297, 149.25, 2029.85, 0]
single_array = np.array(single_sample).reshape(1, -1)
single_scaled = scaler.transform(single_array)

single_pred = best_model.predict(single_scaled)[0]
single_proba = best_model.predict_proba(single_scaled)[0]

print("\nSingle sample prediction:")
print("Predicted class:", single_pred)
for idx, cls in enumerate(best_model.classes_):
    print(f"  Class {cls}: {single_proba[idx]:.4f}")


# ==========================
# 7. File Prediction
# ==========================
pre_file = "Stock Customer Churn - test.xlsx"
df_new = pd.read_excel(pre_file)
X_new = df_new[feature_cols]
X_new_scaled = scaler.transform(X_new)

y_new_pred = best_model.predict(X_new_scaled)
y_new_proba = best_model.predict_proba(X_new_scaled)

df_new["Predicted Class"] = y_new_pred

for idx, cls in enumerate(best_model.classes_):
    df_new[f"Probability of {cls}"] = y_new_proba[:, idx]

output_file = "output.xlsx"
df_new.to_excel(output_file, index=False)

print(f"\nFile prediction completed. Saved to \"{output_file}\".")


# ==========================
# 8. Feature Importance (Coefficient-Based)
# ==========================
print("\nFeature importance (coefficient-based):")

coef = best_model.coef_
importance = np.mean(np.abs(coef), axis=0)

importance_df = pd.DataFrame({
    "Feature": feature_cols,
    "Importance": importance
}).sort_values(by="Importance", ascending=False).reset_index(drop=True)

print(importance_df)
