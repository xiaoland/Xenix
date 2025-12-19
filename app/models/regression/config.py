"""
Configuration file for Xenix ML models.
This file contains configurable parameters for data processing.
"""

# Feature column names for regression tasks
# Default configuration for customer value prediction
FEATURE_COLUMNS = [
    'Historical Loan Amount',
    'Number of Loans',
    'Education',
    'Monthly Income',
    'Gender'
]

# Target column name
TARGET_COLUMN = 'Customer Value'

# Prediction output column name
PREDICTION_COLUMN = 'Predicted Customer Value'

# Default training data file
DEFAULT_TRAINING_DATA = 'Customer Value Data Table.xlsx'
