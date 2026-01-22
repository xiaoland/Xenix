import type { StorageService } from './StorageService';
import { FileSystemStorage } from './FileSystemStorage';
import { config } from '../config';

/**
 * Create unified filesystem storage service
 * Uses STORAGE_BASE_PATH from config (./uploads for dev, /mnt/oss for production)
 */
export function createStorageService(): StorageService {
  return new FileSystemStorage(config.STORAGE_BASE_PATH);
}

// Re-export types and schemas
export * from './StorageService';
export * from './schemas';
export { FileSystemStorage } from './FileSystemStorage';
