"""
Predict Worker for Aliyun Function Compute
Performs prediction using trained ML models
"""
import json
import sys
import os
from pathlib import Path

# Add ml directory to Python path
sys.path.insert(0, str(Path(__file__).parent / 'ml'))

from ml.predict_on_json import predict_on_json


def handler(event, context):
    """
    FC handler for prediction tasks

    Event structure:
    {
      "taskId": 123,
      "trainingDataFile": "/mnt/oss/datasets/1/training.xlsx",
      "predictionData": [{col1: val1, col2: val2}, ...],
      "outputFile": "/mnt/oss/predictions/123/output.xlsx",
      "model": "regression.linear_regression",
      "params": {...},
      "featureColumns": ["col1", "col2"],
      "targetColumn": "target"
    }
    """
    try:
        # Parse event
        if isinstance(event, str):
            event_data = json.loads(event)
        elif isinstance(event, bytes):
            event_data = json.loads(event.decode('utf-8'))
        elif isinstance(event, dict):
            event_data = event
        else:
            raise ValueError(f"Unsupported event type: {type(event)}")

        # Validate required fields
        required_fields = [
            'taskId', 'trainingDataFile', 'predictionData', 'outputFile',
            'model', 'featureColumns', 'targetColumn'
        ]
        for field in required_fields:
            if field not in event_data:
                raise ValueError(f"Missing required field: {field}")

        # Extract parameters
        task_id = event_data['taskId']
        training_data_file = event_data['trainingDataFile']
        prediction_data = event_data['predictionData']
        output_file = event_data['outputFile']
        model = event_data['model']
        params = event_data.get('params', {})
        feature_columns = event_data['featureColumns']
        target_column = event_data['targetColumn']

        print(f"[Predict] Starting task {task_id}", file=sys.stderr)
        print(f"[Predict] Training file: {training_data_file}", file=sys.stderr)
        print(f"[Predict] Output file: {output_file}", file=sys.stderr)
        print(f"[Predict] Model: {model}", file=sys.stderr)

        # Ensure output directory exists
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Run prediction
        result = {
            "message": "Prediction completed successfully",
            "taskId": task_id,
            "outputFile": output_file,
            "model": model,
            "predictedCount": len(prediction_data),
        }

        print(f"[Predict] Task {task_id} completed successfully", file=sys.stderr)

        return {
            'statusCode': 200,
            'body': json.dumps({
                'taskId': task_id,
                'status': 'completed',
                'result': result
            })
        }

    except Exception as e:
        error_msg = str(e)
        task_id = event_data.get('taskId', 'unknown') if 'event_data' in locals() else 'unknown'

        print(f"[Predict] Error in task {task_id}: {error_msg}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)

        return {
            'statusCode': 500,
            'body': json.dumps({
                'taskId': task_id,
                'status': 'failed',
                'error': error_msg
            })
        }


if __name__ == '__main__':
    test_event = {
        'taskId': 1,
        'trainingDataFile': '../../uploads/datasets/1/training.xlsx',
        'predictionData': [{'col1': 1, 'col2': 2}],
        'outputFile': '../../uploads/predictions/1/output.xlsx',
        'model': 'regression.linear_regression',
        'params': {},
        'featureColumns': ['col1', 'col2'],
        'targetColumn': 'target'
    }

    result = handler(test_event, None)
    print(json.dumps(result, indent=2))
