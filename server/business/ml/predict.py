#!/usr/bin/env python3
"""
Batch prediction script using modular model definitions.
Each model is imported as a module with a Model class providing tune(), evaluate(), and predict() methods.
Reads all configuration from stdin JSON (no database interactions).
Outputs structured JSON to stdout.
"""
import json
import sys
import warnings
import pandas as pd
from pathlib import Path

# Suppress warnings
warnings.filterwarnings("ignore")

# Add parent directory to path
sys.path.append(str(Path(__file__).parent))

# Import structured output utilities
from structured_output import get_logger, emit_log

# Import base utilities
from base import import_model


def main():
    """
    Main function that reads JSON input from stdin.
    Expected JSON structure:
    {
        "trainingDataPath": "/path/to/training_data.xlsx",
        "predictionDataPath": "/path/to/prediction_data.xlsx",
        "outputPath": "/path/to/output.xlsx",
        "model": "ridge",
        "params": {"model__alpha": 1.0},
        "featureColumns": ["col1", "col2", "col3"],
        "targetColumn": "target"
    }
    """
    logger = get_logger(__name__)
    
    try:
        # Read input from stdin
        logger.info("Reading input configuration from stdin")
        input_data = json.loads(sys.stdin.read())
        
        # Extract parameters
        training_data_path = input_data.get('trainingDataPath')
        prediction_data_path = input_data.get('predictionDataPath')
        output_path = input_data.get('outputPath')
        model_name = input_data.get('model')
        params = input_data.get('params', {})
        feature_columns = input_data.get('featureColumns')
        target_column = input_data.get('targetColumn')
        
        # Validate required parameters
        if not training_data_path:
            raise ValueError("trainingDataPath is required")
        if not prediction_data_path:
            raise ValueError("predictionDataPath is required")
        if not output_path:
            raise ValueError("outputPath is required")
        if not model_name:
            raise ValueError("model is required")
        if not feature_columns:
            raise ValueError("featureColumns is required")
        if not target_column:
            raise ValueError("targetColumn is required")
        
        logger.info(f"Starting batch prediction using {model_name}")
        logger.info(f"Parameters: {params}")
        
        # Import Model class directly
        logger.info(f"Importing model for {model_name}")
        Model = import_model(model_name)
        
        # Load training data and train model with best parameters
        logger.info(f"Loading training data from {training_data_path}")
        training_df = pd.read_excel(training_data_path)
        logger.info(f"Training data loaded: {len(training_df)} rows")
        
        X_train = training_df[feature_columns]
        y_train = training_df[target_column]
        
        # Create model with tuned parameters using the Model class's create_model method
        logger.info(f"Creating {model_name} with tuned parameters")
        model = Model.create_model(params)
        
        # Train the model on full training dataset
        logger.info("Training model on full training dataset")
        model.fit(X_train, y_train)
        logger.info("Model training completed")
        
        # Load prediction data
        logger.info(f"Loading prediction data from {prediction_data_path}")
        prediction_df = pd.read_excel(prediction_data_path)
        logger.info(f"Prediction data loaded: {len(prediction_df)} rows")
        
        # Make predictions using the Model class's predict method
        logger.info("Generating predictions")
        X_pred = prediction_df[feature_columns]
        predictions = Model.predict(model, X_pred)
        
        # Add predictions to dataframe
        prediction_df['Predicted_Value'] = predictions.values
        logger.info(f"Predictions generated for {len(predictions)} samples")
        
        # Save results
        logger.info(f"Saving predictions to {output_path}")
        prediction_df.to_excel(output_path, index=False)
        logger.info("Predictions saved successfully")
        
        # Emit success status
        emit_log("info", f"Batch prediction completed successfully! Output saved to {output_path}")
        
        # Output result information
        result_info = {
            "type": "prediction_result",
            "data": {
                "output_path": output_path,
                "num_predictions": len(predictions),
                "model": model_name
            }
        }
        print(json.dumps(result_info), flush=True)
        
    except Exception as e:
        logger.error(f"Error during batch prediction: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
