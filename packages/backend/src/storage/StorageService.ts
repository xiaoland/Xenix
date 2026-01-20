import type {
  FileMetadata,
  PresignedUrlRequest,
  PresignedUrlResponse,
} from './schemas';

/**
 * Storage service interface for file operations
 * Supports both local filesystem (development) and Aliyun OSS (production)
 */
export interface StorageService {
  /**
   * Generate presigned URL for frontend to upload file directly to storage
   * @param request - Presigned URL request with key, expiration, and content type
   * @returns Presigned URL response with URL, key, and expiration time
   */
  generatePresignedUploadUrl(
    request: PresignedUrlRequest
  ): Promise<PresignedUrlResponse>;

  /**
   * Generate presigned URL for frontend to download file directly from storage
   * @param key - Storage key
   * @param expiresIn - URL expiration time in seconds (default: 3600)
   * @returns Presigned download URL
   */
  generatePresignedDownloadUrl(key: string, expiresIn?: number): Promise<string>;

  /**
   * Check if file exists in storage
   * @param key - Storage key
   * @returns True if file exists
   */
  exists(key: string): Promise<boolean>;

  /**
   * Delete file from storage
   * @param key - Storage key
   */
  delete(key: string): Promise<void>;

  /**
   * Get file metadata (size, modified time, etc.)
   * @param key - Storage key
   * @returns File metadata
   */
  stat(key: string): Promise<FileMetadata>;

  /**
   * Get filesystem path for file
   * - For local storage: returns absolute path to file
   * - For OSS: returns mount point path (e.g., /mnt/oss/datasets/1/file.xlsx)
   * @param key - Storage key
   * @returns Filesystem path
   */
  getFilesystemPath(key: string): string;

  /**
   * Copy file within storage
   * @param sourceKey - Source storage key
   * @param destKey - Destination storage key
   */
  copy(sourceKey: string, destKey: string): Promise<void>;

  /**
   * Fetch file content from storage
   * @param key - Storage key
   * @param options - Fetch options (timeout, etc.)
   * @returns Response object with file content
   */
  fetch(key: string, options?: { timeout?: number }): Promise<Response>;
}
