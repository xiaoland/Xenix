/**
 * Available machine learning models configuration
 */
export const AVAILABLE_MODELS = [
    {
        label: "Linear Regression",
        value: "regression.linear_regression_hyperparameter_tuning",
    },
    { label: "Ridge", value: "regression.ridge" },
    { label: "Lasso", value: "regression.lasso" },
    { label: "Bayesian Ridge", value: "regression.bayesian_ridge_regression" },
    { label: "KNN", value: "regression.k_nearest_neighbors" },
    { label: "Decision Tree", value: "regression.regression_decision_tree" },
    { label: "Random Forest", value: "regression.random_forest" },
    { label: "GBDT", value: "regression.gbdt" },
    { label: "AdaBoost", value: "regression.adaboost" },
    { label: "XGBoost", value: "regression.xgboost" },
    { label: "LightGBM", value: "regression.lightgbm" },
    { label: "Polynomial", value: "regression.polynomial_regression" },
];
