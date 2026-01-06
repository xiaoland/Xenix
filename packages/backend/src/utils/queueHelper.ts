/**
 * Queue Helper
 * Utility functions for adding jobs to queues
 */
import { randomUUID } from 'crypto';

import type { MLTaskData } from '../jobs/index.js';
import { mlTasksQueue } from '../queues/index.js';
import logger from '../utils/logger/index.js';

export async function addMLTask(data: MLTaskData) {
  const job = await mlTasksQueue.add('ml-task', data, {
    jobId: `ml-task-${data.taskId}-${randomUUID()}`,
  });

  logger.info(
    { jobId: job.id, taskId: data.taskId, type: data.type },
    'Added ML task to queue'
  );

  return job;
}

export async function getJobStatus(jobId: string) {
  const job = await mlTasksQueue.getJob(jobId);

  if (!job) {
    return null;
  }

  const state = await job.getState();
  const progress = job.progress;
  const failedReason = job.failedReason;

  return {
    id: job.id,
    state,
    progress,
    failedReason,
    data: job.data,
  };
}
