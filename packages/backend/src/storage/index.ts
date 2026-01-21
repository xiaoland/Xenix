import type { StorageService } from './StorageService';
import { LocalStorage } from './LocalStorage';
import { OSSStorage } from './OSSStorage';
import { config } from '../config';
import { ossConfigSchema } from './schemas';

/**
 * Create storage service based on storage type
 * - Returns LocalStorage for 'local' storage type
 * - Returns OSSStorage for 'oss' storage type
 */
export function createStorageService(storageType: 'local' | 'oss'): StorageService {
  if (storageType === 'oss') {
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

// Re-export types and schemas
export * from './StorageService';
export * from './schemas';
export { LocalStorage } from './LocalStorage';
export { OSSStorage } from './OSSStorage';
