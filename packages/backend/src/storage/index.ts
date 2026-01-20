import type { StorageService } from './StorageService';
import { LocalStorage } from './LocalStorage';
import { OSSStorage } from './OSSStorage';
import { config } from '../config';
import { ossConfigSchema } from './schemas';

/**
 * Create storage service based on configuration
 * - Returns LocalStorage for development (STORAGE_TYPE=local)
 * - Returns OSSStorage for production (STORAGE_TYPE=oss)
 */
export function createStorageService(): StorageService {
  if (config.STORAGE_TYPE === 'oss') {
    // Validate OSS configuration
    const ossConfig = ossConfigSchema.parse({
      region: config.OSS_REGION,
      accessKeyId: config.OSS_ACCESS_KEY_ID,
      accessKeySecret: config.OSS_ACCESS_KEY_SECRET,
      bucket: config.OSS_BUCKET,
      endpoint: config.OSS_ENDPOINT,
    });

    return new OSSStorage(ossConfig, config.OSS_MOUNT_POINT);
  }

  // Default to local storage
  return new LocalStorage(config.UPLOAD_DIR);
}

/**
 * Singleton storage service instance
 * Import and use this throughout the application
 */
export const storage = createStorageService();

// Re-export types and schemas
export * from './StorageService';
export * from './schemas';
export { LocalStorage } from './LocalStorage';
export { OSSStorage } from './OSSStorage';
