"""Single training controller - delegates to model services"""

from ..types import SingleTrainInput, SingleTrainOutput
from ..services import get_model
from ..utils import read_data
from ..utils.logger import TaskLogger


def single_train(input_data: SingleTrainInput, logger: TaskLogger) -> SingleTrainOutput:
    """
    Single training with specific parameters (no tuning)

    Delegates to the appropriate model service for training.
    NO model saving - models are saved during prediction operations only.

    Args:
        input_data: Single training input parameters
        logger: Task logger instance

    Returns:
        Single training output with metrics (NO model_path)
    """
    logger.log(f"Starting single training for model {input_data.model}", "INFO", {
        "model": input_data.model,
        "features": input_data.feature_columns,
        "targets": input_data.target_columns,
        "params": input_data.params
    })

    try:
        # Read training data
        logger.log(f"Reading training data from {input_data.train_data_path}", "INFO")
        df = read_data(input_data.train_data_path)

        logger.log(f"Training data loaded: {len(df)} rows, {len(df.columns)} columns", "INFO")

        # Get model service
        model_service = get_model(input_data.model)

        logger.log(f"Using model service: {model_service.__class__.__name__}", "INFO")

        # Delegate training to model service
        result = model_service.single_train(df, input_data)

        logger.log(f"Model metrics: {result['metrics']}", "INFO")

        # Return result WITHOUT model_path (models saved in predict operations only)
        output = SingleTrainOutput(
            metrics=result['metrics']
        )

        logger.log("Single training completed successfully", "INFO")
        return output

    except Exception as e:
        logger.log(f"Single training failed: {str(e)}", "ERROR", {"error": str(e)})
        raise
