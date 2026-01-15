# -*- coding: utf-8 -*-
"""
AdaBoost Classification Model with Hyperparameter Tuning
for Stock Customer Churn

Notes:
- AdaBoost uses DecisionTreeClassifier as default base estimator, which is not
  sensitive to feature scaling. Therefore, NO normalization is applied.
- The parameter grid follows the SAME STYLE as previous models.
- SAMME.R is deprecated in sklearn; we explicitly use SAMME to avoid warnings.

Steps:
1. No normalization (tree-based base estimator does not need it).
2. Hyperparameter tuning with GridSearchCV.
3. Save best parameters into JSON.
4. Model evaluation (Accuracy, Precision, Recall, F1 Score, AUC).
5. Single-sample prediction (multi-class compatible).
6. Excel file prediction and output to output.xlsx.
7. Feature importance (feature_importances_ or permutation importance).
8. Ignore warnings.
"""

import warnings
warnings.filterwarnings("ignore")  # Ignore all warnings

import json
import numpy as np
import pandas as pd

from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.ensemble import AdaBoostClassifier
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score
)
from sklearn.inspection import permutation_importance

# ==========================
# 1. Read data
# ==========================
input_file = "Stock Customer Churn.xlsx"
df = pd.read_excel(input_file)

# X = all features; y = target
X = df.drop(columns="Customer Churn (Yes/No)")
y = df["Customer Churn (Yes/No)"]

feature_cols = X.columns.tolist()

# ==========================
# 2. Train-test split (no normalization)
# ==========================
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=0,
    stratify=y
)

# ==========================
# 3. Hyperparameter tuning (Unified style)
# ==========================
base_model = AdaBoostClassifier(
    algorithm="SAMME",   # use SAMME to avoid SAMME.R deprecation warning
    random_state=0
)

param_grid = {
    "n_estimators": [50, 100, 200],
    "learning_rate": [0.01, 0.1, 0.5, 1.0],
    "algorithm": ["SAMME"]   # only SAMME (recommended here)
}

grid_search = GridSearchCV(
    estimator=base_model,
    param_grid=param_grid,
    scoring="f1_weighted",
    cv=5,
    n_jobs=-1,
    verbose=0
)

grid_search.fit(X_train, y_train)

best_model = grid_search.best_estimator_
best_params = grid_search.best_params_

# ==========================
# 4. Save tuned parameters to JSON
# ==========================
json_filename = "AdaBoost_Classification_Model_Params.json"
with open(json_filename, "w", encoding="utf-8") as f:
    json.dump(best_params, f, indent=4)

print("Best tuned parameters:")
print(best_params)
print(f"Tuned parameters saved to: {json_filename}")

# ==========================
# 5. Evaluation (robust for binary & multiclass)
# ==========================
y_pred = best_model.predict(X_test)
y_proba = best_model.predict_proba(X_test)

# Decide if true problem is binary or multi-class based on TRAINING set
true_classes = np.unique(y_train)
n_true_classes = len(true_classes)

accuracy = accuracy_score(y_test, y_pred)

if n_true_classes == 2:
    # ------- TRUE BINARY CLASSIFICATION -------
    precision = precision_score(y_test, y_pred, zero_division=0)
    recall = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)

    # positive class = larger label
    pos_class = sorted(true_classes)[1]
    pos_index = list(best_model.classes_).index(pos_class)
    auc_value = roc_auc_score(y_test, y_proba[:, pos_index])

else:
    # ------- TRUE MULTI-CLASS CLASSIFICATION -------
    precision = precision_score(y_test, y_pred, average="weighted", zero_division=0)
    recall = recall_score(y_test, y_pred, average="weighted", zero_division=0)
    f1 = f1_score(y_test, y_pred, average="weighted", zero_division=0)

    # labels actually present in THIS test set
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
        col_indices = [classes_model.index(lbl) for lbl in test_labels]
        y_proba_aligned = y_proba[:, col_indices]

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
# 6. Single Sample Prediction
# ==========================
single_sample = [22686.5, 297, 149.25, 2029.85, 0]
single_array = np.array(single_sample).reshape(1, -1)

single_pred = best_model.predict(single_array)[0]
single_proba = best_model.predict_proba(single_array)[0]

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

y_new_pred = best_model.predict(X_new)
y_new_proba = best_model.predict_proba(X_new)

df_new["Predicted Class"] = y_new_pred

for idx, cls in enumerate(best_model.classes_):
    df_new[f"Probability of {cls}"] = y_new_proba[:, idx]

output_file = "output.xlsx"
df_new.to_excel(output_file, index=False)

print(f"\nFile prediction completed. Saved to \"{output_file}\".")

# ==========================
# 8. Feature Importance
# ==========================
print("\nFeature importance (sorted from high to low):")

if hasattr(best_model, "feature_importances_"):
    print("Using model.feature_importances_ from AdaBoost.")
    importance = best_model.feature_importances_
else:
    print("Model does NOT have feature_importances_. Using permutation importance instead.")
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
