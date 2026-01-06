/**
 * Queue Configuration
 * Centralized Redis connection and queue setup
 */

import { Queue, QueueEvents } from 'bullmq';
import { config } from '../config/index.js';
import logger from '../utils/logger/index.js';

// Parse Redis URL once
const redisUrl = new URL(config.REDIS_URL);

// Redis connection configuration
export const connection = {
  host: redisUrl.hostname,
  port: Number(redisUrl.port) || 6379,
};

// Queue names
export const QUEUE_NAMES = {
  ML_TASKS: 'ml-tasks',
} as const;

// Create ML tasks queue
export const mlTasksQueue = new Queue(QUEUE_NAMES.ML_TASKS, {
  connection,
  defaultJobOptions: {
    attempts: 3,
    backoff: {
      type: 'exponential',
      delay: 2000,
    },
    removeOnComplete: {
      age: 24 * 3600, // Keep completed jobs for 24 hours
      count: 1000,
    },
    removeOnFail: {
      age: 7 * 24 * 3600, // Keep failed jobs for 7 days
    },
  },
});

// Queue events for monitoring
export const mlTasksQueueEvents = new QueueEvents(QUEUE_NAMES.ML_TASKS, {
  connection,
});

mlTasksQueueEvents.on('completed', ({ jobId }) => {
  logger.info({ jobId }, 'Job completed');
});

mlTasksQueueEvents.on('failed', ({ jobId, failedReason }) => {
  logger.error({ jobId, failedReason }, 'Job failed');
});

logger.info('BullMQ queues initialized');
