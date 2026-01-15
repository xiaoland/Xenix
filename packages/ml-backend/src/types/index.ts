/**
 * Logger interface for ML operations
 * Supports structured logging to database
 */
export interface MLLogger {
  log(
    message: string,
    level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL',
    attributes?: Record<string, any>
  ): Promise<void>;
}

/**
 * Input for batch training (GridSearchCV auto-tuning)
 */
export interface BatchTrainInput {
  inputFile: string; // Path to training data (Excel/CSV)
  model: string; // Model name (e.g., 'regression.ridge')
  featureColumns: string[]; // Feature column names
  targetColumn: string; // Target column name
  paramGrid: Record<string, any[]>; // Parameter grid for GridSearchCV
  taskId: number; // Task ID for logging
  logger: MLLogger; // Logger instance
}

/**
 * Output from batch training
 */
export interface BatchTrainOutput {
  bestParams: Record<string, any>; // Best parameters found
  fittedModel: any; // Serialized model (could be base64 or pickle)
  metrics: {
    mse: number; // Mean Squared Error
    mae: number; // Mean Absolute Error
    r2: number; // R² Score
  };
}

/**
 * Input for single training (specific parameters)
 */
export interface SingleTrainInput {
  inputFile: string;
  model: string;
  featureColumns: string[];
  targetColumn: string;
  params: Record<string, any>; // Single parameter set
  taskId: number;
  logger: MLLogger;
  parentTaskId?: number; // Optional parent task (if this is a single-train from batch-train)
}

/**
 * Output from single training
 */
export interface SingleTrainOutput {
  metrics: {
    mse: number;
    mae: number;
    r2: number;
  };
  fittedModel: any; // Serialized model
}

/**
 * Input for prediction
 */
export interface PredictInput {
  trainData: string; // Path to training data
  predictData: string | any[]; // Path to prediction data OR inline JSON array
  outputPath: string; // Where to save predictions
  model: string;
  params: Record<string, any>;
  featureColumns: string[];
  targetColumn: string;
  taskId: number;
  logger: MLLogger;
}

/**
 * Output from prediction
 */
export interface PredictOutput {
  predictedData: any[]; // Predictions (array or file path)
  fittedModel: any; // Serialized model
  metrics?: {
    // Optional metrics if test data available
    mse: number;
    mae: number;
    r2: number;
  };
}

/**
 * Options for Python executor
 */
export interface PythonExecutorOptions {
  script: string; // Path to Python script
  stdinData: any; // JSON data to pass via stdin
  taskId: number; // Task ID for logging
  cwd?: string; // Working directory
  onLog?: (log: StructuredLog) => Promise<void>; // Callback for structured logs
  onResult?: (result: any) => Promise<void>; // Callback for result
}

/**
 * Structured output from Python scripts
 */
export interface StructuredOutput {
  type: 'log' | 'status' | 'result';
  data: any;
}

/**
 * Structured log entry (OpenTelemetry format)
 */
export interface StructuredLog {
  timestamp: number; // Nanoseconds
  observed_timestamp: number; // Nanoseconds
  severity_text: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL';
  severity_number: number; // OpenTelemetry severity number
  body: string; // Log message
  resource?: {
    'service.name': string;
    'service.version': string;
  };
  attributes?: Record<string, any>;
}
