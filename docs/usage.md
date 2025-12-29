# Usage Guide

### Step 1: Upload & Train

1. **Upload Training Data**
   - Upload an Excel file (.xlsx or .xls) containing your training data
   - The file should have feature columns and a target variable column
   - Example: `Customer Value Data Table.xlsx`

2. **Select & Tune Models**
   - Select one or more models to tune from the 12 available options
   - Click "Start Hyperparameter Tuning" to begin Grid SearchCV optimization
   - Watch real-time logs as models train
   - Wait for tuning to complete (status updates automatically)

3. **View Results & Select Best Model**
   - See evaluation metrics table with MSE, MAE, and R² scores
   - Table automatically sorts by R² (best first)
   - Click radio button to select the model you want to use
   - Click "Continue to Prediction"

### Step 2: Predict

1. **Upload Prediction Data**
   - Upload a new Excel file with the same features (without the target variable)
   - Must have same column names as training data

2. **Generate Predictions**
   - Click "Start Prediction" to run the selected model
   - Wait for prediction to complete
   - Download the results with predictions added as a new column
