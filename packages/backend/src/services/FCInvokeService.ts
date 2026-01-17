/**
 * Aliyun Function Compute Invocation Service
 * Handles async invocation of Python ML worker functions
 */
import FCClient from '@alicloud/fc2';
import { z } from 'zod';
import { config } from '../config';
import logger from '../utils/logger';

// Zod schema for FC invoke request
const fcInvokeRequestSchema = z.object({
  functionName: z.string(),
  payload: z.record(z.any()),
  invocationType: z.enum(['Sync', 'Async']).default('Async'),
  serviceName: z.string().default('xenix'),
});

export type FCInvokeRequest = z.infer<typeof fcInvokeRequestSchema>;

/**
 * Service for invoking Aliyun FC functions asynchronously
 */
export class FCInvokeService {
  private client: FCClient | null = null;
  private readonly serviceName: string;

  constructor(serviceName = 'xenix') {
    this.serviceName = serviceName;

    // Only initialize FC client in production (when OSS config is available)
    if (config.STORAGE_TYPE === 'oss' && config.OSS_REGION && config.OSS_ACCESS_KEY_ID && config.OSS_ACCESS_KEY_SECRET) {
      this.client = new FCClient(config.OSS_REGION, {
        accessKeyID: config.OSS_ACCESS_KEY_ID,
        accessKeySecret: config.OSS_ACCESS_KEY_SECRET,
        timeout: 60000, // 60 seconds timeout for invocation request
      });

      logger.info({ region: config.OSS_REGION, serviceName }, 'FC client initialized');
    } else {
      logger.warn('FC client not initialized - running in local mode');
    }
  }

  /**
   * Invoke FC function asynchronously
   * @param request - Invocation request with function name and payload
   */
  async invokeAsync(request: FCInvokeRequest): Promise<void> {
    if (!this.client) {
      logger.warn(
        { functionName: request.functionName },
        'FC client not available - skipping invocation (local mode)'
      );
      return;
    }

    // Validate request
    const validated = fcInvokeRequestSchema.parse({
      ...request,
      serviceName: request.serviceName || this.serviceName,
    });

    try {
      logger.info(
        {
          serviceName: validated.serviceName,
          functionName: validated.functionName,
          invocationType: validated.invocationType,
          taskId: validated.payload.taskId,
        },
        'Invoking FC function'
      );

      // Invoke function
      await this.client.invokeFunction(
        validated.serviceName,
        validated.functionName,
        Buffer.from(JSON.stringify(validated.payload)),
        {
          'X-Fc-Invocation-Type': validated.invocationType,
        }
      );

      logger.info(
        {
          serviceName: validated.serviceName,
          functionName: validated.functionName,
          taskId: validated.payload.taskId,
        },
        'FC function invoked successfully'
      );
    } catch (error: any) {
      logger.error(
        {
          error: error.message,
          serviceName: validated.serviceName,
          functionName: validated.functionName,
          taskId: validated.payload.taskId,
        },
        'Failed to invoke FC function'
      );
      throw error;
    }
  }

  /**
   * Check if FC client is available
   */
  isAvailable(): boolean {
    return this.client !== null;
  }
}

/**
 * Singleton instance
 */
export const fcInvokeService = new FCInvokeService();
