import path from 'path';
import { fileURLToPath } from 'url';
import type {
  SingleTrainInput,
  SingleTrainOutput,
  StructuredLog,
} from '../types';
import { executePython } from '../utils/python-executor';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/**
 * Single training with specific parameters (manual tuning)
 * Trains a model with a specific set of hyperparameters
 */
export async function singleTrain(
  input: SingleTrainInput
): Promise<SingleTrainOutput> {
  const {
    inputFile,
    model,
    featureColumns,
    targetColumn,
    params,
    taskId,
    logger,
    parentTaskId,
  } = input;

  // Path to the Python script
  const scriptPath = path.join(
    __dirname,
    '..',
    'python',
    'manual_tune_model.py'
  );

  // Prepare stdin data for Python script
  const stdinData = {
    task_id: taskId,
    input_file: inputFile,
    model,
    feature_columns: featureColumns,
    target_column: targetColumn,
    params,
    parent_task_id: parentTaskId,
  };

  // Log start
  await logger.log(
    `Starting single training for model ${model}`,
    'INFO',
    { model, features: featureColumns, target: targetColumn, params }
  );

  try {
    // Execute Python script with structured logging
    const result = await executePython<SingleTrainOutput>({
      script: scriptPath,
      stdinData,
      taskId,
      onLog: async (log: StructuredLog) => {
        // Forward Python logs to our logger
        await logger.log(log.body, log.severity_text, log.attributes);
      },
      onResult: async (resultData: any) => {
        // Log when result is received
        await logger.log('Single training completed successfully', 'INFO', {
          metrics: resultData.metrics,
        });
      },
    });

    return result;
  } catch (error) {
    // Log error
    await logger.log(
      `Single training failed: ${error instanceof Error ? error.message : 'Unknown error'}`,
      'ERROR',
      { error: error instanceof Error ? error.stack : String(error) }
    );
    throw error;
  }
}
