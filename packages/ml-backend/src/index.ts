/**
 * @xenix/ml-backend
 *
 * Standalone ML backend package for Xenix
 * Provides machine learning operations (training, prediction) with multiple delivery adapters
 */

// Core ML operations
export { batchTrain } from './core/batch-train';
export { singleTrain } from './core/single-train';
export { predict } from './core/predict';

// Types
export type {
  MLLogger,
  BatchTrainInput,
  BatchTrainOutput,
  SingleTrainInput,
  SingleTrainOutput,
  PredictInput,
  PredictOutput,
  PythonExecutorOptions,
  StructuredOutput,
  StructuredLog,
} from './types';

// Utilities
export { DatabaseLogger, ConsoleLogger, createLogger } from './utils/logger';
export type { LoggerConfig } from './utils/logger';
export { executePython, executePythonSync } from './utils/python-executor';
