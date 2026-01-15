import path from 'path';
import { fileURLToPath } from 'url';
import type { PredictInput, PredictOutput, StructuredLog } from '../types';
import { executePython } from '../utils/python-executor';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/**
 * Make predictions using a trained model
 * Supports both file-based and inline JSON prediction data
 */
export async function predict(input: PredictInput): Promise<PredictOutput> {
  const {
    trainData,
    predictData,
    outputPath,
    model,
    params,
    featureColumns,
    targetColumn,
    taskId,
    logger,
  } = input;

  // Determine which Python script to use based on input type
  const isInlineData = Array.isArray(predictData);
  const scriptName = isInlineData ? 'predict_on_json.py' : 'predict.py';
  const scriptPath = path.join(__dirname, '..', 'python', scriptName);

  // Prepare stdin data for Python script
  const stdinData = isInlineData
    ? {
        task_id: taskId,
        training_data_path: trainData,
        prediction_data: predictData,
        output_path: outputPath,
        model,
        params,
        feature_columns: featureColumns,
        target_column: targetColumn,
      }
    : {
        task_id: taskId,
        training_data_path: trainData,
        prediction_data_path: predictData,
        output_path: outputPath,
        model,
        params,
        feature_columns: featureColumns,
        target_column: targetColumn,
      };

  // Log start
  await logger.log(
    `Starting prediction for model ${model}`,
    'INFO',
    {
      model,
      features: featureColumns,
      target: targetColumn,
      isInlineData,
    }
  );

  try {
    // Execute Python script with structured logging
    const result = await executePython<PredictOutput>({
      script: scriptPath,
      stdinData,
      taskId,
      onLog: async (log: StructuredLog) => {
        // Forward Python logs to our logger
        await logger.log(log.body, log.severity_text, log.attributes);
      },
      onResult: async (resultData: any) => {
        // Log when result is received
        await logger.log('Prediction completed successfully', 'INFO', {
          outputPath: resultData.outputPath || resultData.predictedData?.length,
        });
      },
    });

    return result;
  } catch (error) {
    // Log error
    await logger.log(
      `Prediction failed: ${error instanceof Error ? error.message : 'Unknown error'}`,
      'ERROR',
      { error: error instanceof Error ? error.stack : String(error) }
    );
    throw error;
  }
}
