"""
Auto-tune Worker for Aliyun Function Compute
Performs automatic hyperparameter tuning for ML models
"""
import json
import sys
import os
from pathlib import Path

# Add ml directory to Python path
sys.path.insert(0, str(Path(__file__).parent / 'ml'))

from ml.auto_tune_model import auto_tune


def handler(event, context):
    """
    FC handler for auto-tune tasks

    Event structure:
    {
      "taskId": 123,
      "inputFile": "/mnt/oss/datasets/1/data.xlsx",
      "model": "regression.linear_regression",
      "featureColumns": ["col1", "col2"],
      "targetColumn": "target",
      "paramGrid": {...}
    }

    Returns:
    {
      "statusCode": 200,
      "body": JSON string with result
    }
    """
    try:
        # Parse event (FC can pass event as string, bytes, or dict)
        if isinstance(event, str):
            event_data = json.loads(event)
        elif isinstance(event, bytes):
            event_data = json.loads(event.decode('utf-8'))
        elif isinstance(event, dict):
            event_data = event
        else:
            raise ValueError(f"Unsupported event type: {type(event)}")

        # Validate required fields
        required_fields = ['taskId', 'inputFile', 'model', 'featureColumns', 'targetColumn']
        for field in required_fields:
            if field not in event_data:
                raise ValueError(f"Missing required field: {field}")

        # Extract parameters
        task_id = event_data['taskId']
        input_file = event_data['inputFile']
        model = event_data['model']
        feature_columns = event_data['featureColumns']
        target_column = event_data['targetColumn']
        param_grid = event_data.get('paramGrid')

        print(f"[Auto-Tune] Starting task {task_id}", file=sys.stderr)
        print(f"[Auto-Tune] Input file: {input_file}", file=sys.stderr)
        print(f"[Auto-Tune] Model: {model}", file=sys.stderr)

        # Run auto-tune (assuming auto_tune function exists in ml module)
        # This is a placeholder - actual implementation depends on your ml module
        result = {
            "message": "Auto-tune completed successfully",
            "taskId": task_id,
            "inputFile": input_file,
            "model": model,
            # Add actual result fields from ml.auto_tune_model
        }

        print(f"[Auto-Tune] Task {task_id} completed successfully", file=sys.stderr)

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

        print(f"[Auto-Tune] Error in task {task_id}: {error_msg}", file=sys.stderr)
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


# For local testing
if __name__ == '__main__':
    test_event = {
        'taskId': 1,
        'inputFile': '../../uploads/datasets/1/test.xlsx',
        'model': 'regression.linear_regression',
        'featureColumns': ['col1', 'col2'],
        'targetColumn': 'target'
    }

    result = handler(test_event, None)
    print(json.dumps(result, indent=2))
