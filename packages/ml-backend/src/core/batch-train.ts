import path from 'path';
import { fileURLToPath } from 'url';
import type { BatchTrainInput, BatchTrainOutput, StructuredLog } from '../types';
import { executePython } from '../utils/python-executor';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/**
 * Batch training with GridSearchCV (auto-tuning)
 * Finds the best hyperparameters for a given model
 */
export async function batchTrain(
  input: BatchTrainInput
): Promise<BatchTrainOutput> {
  const {
    inputFile,
    model,
    featureColumns,
    targetColumn,
    paramGrid,
    taskId,
    logger,
  } = input;

  // Path to the Python script
  const scriptPath = path.join(__dirname, '..', 'python', 'auto_tune_model.py');

  // Prepare stdin data for Python script
  const stdinData = {
    task_id: taskId,
    input_file: inputFile,
    model,
    feature_columns: featureColumns,
    target_column: targetColumn,
    param_grid: paramGrid,
  };

  // Log start
  await logger.log(
    `Starting batch training for model ${model}`,
    'INFO',
    { model, features: featureColumns, target: targetColumn }
  );

  try {
    // Execute Python script with structured logging
    const result = await executePython<BatchTrainOutput>({
      script: scriptPath,
      stdinData,
      taskId,
      onLog: async (log: StructuredLog) => {
        // Forward Python logs to our logger
        await logger.log(log.body, log.severity_text, log.attributes);
      },
      onResult: async (resultData: any) => {
        // Log when result is received
        await logger.log('Batch training completed successfully', 'INFO', {
          metrics: resultData.metrics,
        });
      },
    });

    return result;
  } catch (error) {
    // Log error
    await logger.log(
      `Batch training failed: ${error instanceof Error ? error.message : 'Unknown error'}`,
      'ERROR',
      { error: error instanceof Error ? error.stack : String(error) }
    );
    throw error;
  }
}
