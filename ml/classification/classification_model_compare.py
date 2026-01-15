# -*- coding: utf-8 -*-
"""
Unified Comparison of 9 Classification Models
Output: Full comparison table + Excel file: 9_Classification_Model_Compare.xlsx
"""

import warnings
warnings.filterwarnings("ignore")

import os
import json
import numpy as np
import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.ensemble import (
    RandomForestClassifier,
    AdaBoostClassifier,
    GradientBoostingClassifier
)
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score
)

from xgboost import XGBClassifier
from lightgbm import LGBMClassifier


# ============================================================
# 1. Load Data
# ============================================================
df = pd.read_excel("Stock Customer Churn.xlsx")

X = df.drop(columns="Customer Churn (Yes/No)")
y = df["Customer Churn (Yes/No)"]

feature_cols = X.columns.tolist()
n_classes = y.nunique()  # global number of classes (for choosing metric mode)


# ============================================================
# 2. Train-Test Split
# ============================================================
X_train, X_test, y_train, y_test = train_test_split(
    X, y,
    test_size=0.2,
    random_state=0,
    stratify=y
)


# ============================================================
# 3. Standardization for specific models
# ============================================================
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)


# ============================================================
# Function: Load model parameters if JSON exists
# ============================================================
def load_json(json_file):
    """Load JSON parameters if file exists, otherwise return empty dict."""
    return json.load(open(json_file, "r", encoding="utf-8")) if os.path.exists(json_file) else {}


# ============================================================
# 4. Model Configurations
#    (model_name, model_class, json_file, use_scaled)
# ============================================================
models = [
    ("Logistic Regression", LogisticRegression, "Logistic_Regression_Params.json", True),
    ("Classification Decision Tree", DecisionTreeClassifier, "Classification_Decision_Tree_Params.json", False),
    ("Naive Bayes Model", GaussianNB, "Naive_Bayes_Model_Params.json", True),
    ("KNN Classification Model", KNeighborsClassifier, "K-Nearest_Neighbors_Classification_Model_Params.json", True),
    ("Random Forest", RandomForestClassifier, "Random_Forest_Classification_Model_Params.json", False),
    ("AdaBoost", AdaBoostClassifier, "AdaBoost_Classification_Model_Params.json", False),
    ("GBDT", GradientBoostingClassifier, "GBDT_Classification_Model_Params.json", False),
    ("XGBoost", XGBClassifier, "XGBoost_Classification_Model_Params.json", False),
    ("LightGBM", LGBMClassifier, "LightGBM_Classification_Model_Params.json", False),
]


# ============================================================
# 5. Compare Models
# ============================================================
results = []

for model_name, model_class, json_file, use_scaled in models:

    # ------------------------
    # Load tuned parameters
    # ------------------------
    params = load_json(json_file)

    # Model-specific default additions (do NOT overwrite tuned JSON keys)
    if model_class is XGBClassifier:
        params.setdefault("use_label_encoder", False)
        params.setdefault("eval_metric", "logloss")
        params.setdefault("n_jobs", -1)
        params.setdefault("random_state", 0)

    elif model_class is LGBMClassifier:
        params.setdefault("random_state", 0)
        params.setdefault("n_jobs", -1)
        params.setdefault("verbose", -1)

    # ------------------------
    # Build model
    # ------------------------
    model = model_class(**params)

    # ------------------------
    # Choose scaled or original data
    # ------------------------
    Xtr = X_train_scaled if use_scaled else X_train
    Xte = X_test_scaled if use_scaled else X_test

    # ------------------------
    # Fit model
    # ------------------------
    model.fit(Xtr, y_train)

    # ------------------------
    # Predictions
    # ------------------------
    y_pred = model.predict(Xte)

    if hasattr(model, "predict_proba"):
        y_proba = model.predict_proba(Xte)
        has_proba = True
    else:
        y_proba = None
        has_proba = False

    classes_model = list(model.classes_)
    test_labels = np.unique(y_test)  # labels actually present in the test set

    # ------------------------
    # Metrics: Accuracy
    # ------------------------
    acc = accuracy_score(y_test, y_pred)

    # ------------------------
    # Metrics: Precision / Recall / F1
    # ------------------------
    if n_classes == 2:
        # Global binary classification -> use standard binary metrics
        prec = precision_score(y_test, y_pred, zero_division=0)
        rec = recall_score(y_test, y_pred, zero_division=0)
        f1 = f1_score(y_test, y_pred, zero_division=0)
    else:
        # Global multi-class -> use weighted metrics
        prec = precision_score(y_test, y_pred, average="weighted", zero_division=0)
        rec = recall_score(y_test, y_pred, average="weighted", zero_division=0)
        f1 = f1_score(y_test, y_pred, average="weighted", zero_division=0)

    # ------------------------
    # Metrics: AUC (robust for multi-class and missing classes)
    # ------------------------
    if not has_proba:
        # If model has no probability estimates, AUC is not applicable
        auc = float("nan")
    else:
        # If test set has fewer than 2 classes, AUC is undefined
        if len(test_labels) < 2:
            auc = float("nan")
        # Binary test labels -> treat as binary AUC
        elif len(test_labels) == 2:
            pos_class = sorted(test_labels)[1]               # choose larger label as positive
            pos_index = classes_model.index(pos_class)       # find corresponding column index
            auc = roc_auc_score(y_test, y_proba[:, pos_index])
        else:
            # True multi-class case (3 or more labels in test set)
            # Need to align probability columns with test_labels
            col_indices = [classes_model.index(lbl) for lbl in test_labels]
            y_proba_aligned = y_proba[:, col_indices]

            auc = roc_auc_score(
                y_test,
                y_proba_aligned,
                multi_class="ovr",
                average="weighted"
            )

    # ------------------------
    # Save results
    # ------------------------
    results.append([model_name, acc, prec, rec, f1, auc])


# ============================================================
# 6. Output the Final Comparison Table
# ============================================================
results_df = pd.DataFrame(
    results,
    columns=["Model", "Accuracy", "Precision", "Recall", "F1 Score", "AUC"]
)

# Sort by F1 Score
results_df = results_df.sort_values(by="F1 Score", ascending=False)

# Show full output (no truncation)
pd.set_option("display.max_rows", None)
pd.set_option("display.max_columns", None)
pd.set_option("display.width", None)
pd.set_option("display.max_colwidth", None)

print("\n====================== FINAL MODEL COMPARISON ======================\n")
print(results_df)


# ============================================================
# 7. Save to Excel
# ============================================================
output_excel = "9_Classification_Model_Compare.xlsx"
results_df.to_excel(output_excel, index=False)

print(f"\nComparison results have been saved to: {output_excel}\n")
