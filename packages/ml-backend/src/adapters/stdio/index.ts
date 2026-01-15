/**
 * stdio Adapter
 *
 * Adapter for local development and testing
 * Reads JSON from stdin, executes ML operation, writes result to stdout
 */

import { batchTrain } from '../../core/batch-train';
import { singleTrain } from '../../core/single-train';
import { predict } from '../../core/predict';
import { createLogger } from '../../utils/logger';

/**
 * Main handler for stdio adapter
 * Reads operation from stdin and executes it
 */
export async function handleStdio() {
  try {
    // Read JSON from stdin
    const input = await readStdin();

    // Validate input
    if (!input.operation || !input.taskId) {
      throw new Error('Missing required fields: operation, taskId');
    }

    const { operation, taskId, databaseUrl, ...params } = input;

    // Create logger
    const logger = createLogger(taskId, { databaseUrl });

    // Execute operation
    let result: any;
    switch (operation) {
      case 'batch-train':
        result = await batchTrain({ ...params, taskId, logger });
        break;

      case 'single-train':
        result = await singleTrain({ ...params, taskId, logger });
        break;

      case 'predict':
        result = await predict({ ...params, taskId, logger });
        break;

      default:
        throw new Error(`Unknown operation: ${operation}`);
    }

    // Write result to stdout
    console.log(JSON.stringify({ type: 'result', data: result }));
    process.exit(0);
  } catch (error) {
    // Write error to stderr
    console.error(
      JSON.stringify({
        type: 'error',
        data: {
          message: error instanceof Error ? error.message : 'Unknown error',
          stack: error instanceof Error ? error.stack : undefined,
        },
      })
    );
    process.exit(1);
  }
}

/**
 * Read JSON from stdin
 */
function readStdin(): Promise<any> {
  return new Promise((resolve, reject) => {
    let data = '';

    process.stdin.setEncoding('utf8');

    process.stdin.on('data', (chunk) => {
      data += chunk;
    });

    process.stdin.on('end', () => {
      try {
        const parsed = JSON.parse(data);
        resolve(parsed);
      } catch (error) {
        reject(new Error(`Failed to parse stdin JSON: ${error}`));
      }
    });

    process.stdin.on('error', (error) => {
      reject(new Error(`Failed to read stdin: ${error}`));
    });
  });
}

// If this module is run directly, execute the handler
if (import.meta.url === `file://${process.argv[1]}`) {
  handleStdio().catch((error) => {
    console.error('Fatal error:', error);
    process.exit(1);
  });
}
