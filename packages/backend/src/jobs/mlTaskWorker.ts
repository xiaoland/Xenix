/**
 * ML Task Worker
 * Worker process that consumes jobs from the ML tasks queue
 */
import { Worker } from 'bullmq';

import { QUEUE_NAMES, connection } from '../queues/index.js';
import logger from '../utils/logger/index.js';
import { MLTaskData, processMLTask } from './mlTaskProcessor.js';

// Create worker
export const mlTaskWorker = new Worker<MLTaskData>(
  QUEUE_NAMES.ML_TASKS,
  async (job) => {
    return await processMLTask(job);
  },
  {
    connection,
    concurrency: 2, // Process 2 jobs concurrently
    limiter: {
      max: 10, // Max 10 jobs per duration
      duration: 60000, // per 60 seconds
    },
  }
);

mlTaskWorker.on('completed', (job) => {
  logger.info({ jobId: job.id }, 'Worker completed job');
});

mlTaskWorker.on('failed', (job, err) => {
  logger.error({ jobId: job?.id, error: err }, 'Worker failed to process job');
});

mlTaskWorker.on('error', (err) => {
  logger.error({ error: err }, 'Worker error');
});

logger.info('ML task worker started');

// Graceful shutdown
process.on('SIGTERM', async () => {
  logger.info('SIGTERM received, closing worker');
  await mlTaskWorker.close();
});
