/**
 * Queue Configuration
 * Centralized Redis connection and queue setup
 */
import { Queue, QueueEvents } from "bullmq";

import { config } from "../config";
import { QUEUE_CONFIG, REDIS_DEFAULTS } from "../constants/config";
import logger from "../utils/logger";

// Parse Redis URL once
const redisUrl = new URL(config.REDIS_URL);

// Redis connection configuration
export const connection = {
  host: redisUrl.hostname,
  port: Number(redisUrl.port) || REDIS_DEFAULTS.PORT,
};

// Queue names
export const QUEUE_NAMES = {
  ML_TASKS: "ml-tasks",
} as const;

// Create ML tasks queue
export const mlTasksQueue = new Queue(QUEUE_NAMES.ML_TASKS, {
  connection,
  defaultJobOptions: {
    attempts: 3,
    backoff: {
      type: "exponential",
      delay: QUEUE_CONFIG.RETRY_DELAY,
    },
    removeOnComplete: {
      age: QUEUE_CONFIG.COMPLETED_JOB_AGE,
      count: QUEUE_CONFIG.COMPLETED_JOB_COUNT,
    },
    removeOnFail: {
      age: QUEUE_CONFIG.FAILED_JOB_AGE,
    },
  },
});

// Queue events for monitoring
export const mlTasksQueueEvents = new QueueEvents(QUEUE_NAMES.ML_TASKS, {
  connection,
});

mlTasksQueueEvents.on("completed", ({ jobId }) => {
  logger.info({ jobId }, "Job completed");
});

mlTasksQueueEvents.on("failed", ({ jobId, failedReason }) => {
  logger.error({ jobId, failedReason }, "Job failed");
});

logger.info("BullMQ queues initialized");
