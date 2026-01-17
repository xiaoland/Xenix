import OSS from 'ali-oss';
import path from 'path';
import fs from 'fs/promises';
import type { StorageService } from './StorageService';
import type {
  FileMetadata,
  PresignedUrlRequest,
  PresignedUrlResponse,
  OSSConfig,
} from './schemas';

/**
 * Aliyun OSS storage implementation
 * Used for production environment with OSS mounted as filesystem
 */
export class OSSStorage implements StorageService {
  private client: OSS;
  private mountPoint: string;

  constructor(config: OSSConfig, mountPoint = '/mnt/oss') {
    this.client = new OSS({
      region: config.region,
      accessKeyId: config.accessKeyId,
      accessKeySecret: config.accessKeySecret,
      bucket: config.bucket,
      endpoint: config.endpoint,
    });
    this.mountPoint = mountPoint;
  }

  async generatePresignedUploadUrl(
    request: PresignedUrlRequest
  ): Promise<PresignedUrlResponse> {
    // Generate presigned PUT URL for direct upload from frontend
    const url = this.client.signatureUrl(request.key, {
      method: 'PUT',
      expires: request.expiresIn,
      'Content-Type': request.contentType,
    });

    const expiresAt = new Date(Date.now() + request.expiresIn * 1000);

    return {
      url,
      key: request.key,
      expiresAt,
    };
  }

  async generatePresignedDownloadUrl(
    key: string,
    expiresIn = 3600
  ): Promise<string> {
    // Generate presigned GET URL for direct download from frontend
    return this.client.signatureUrl(key, {
      method: 'GET',
      expires: expiresIn,
    });
  }

  async exists(key: string): Promise<boolean> {
    try {
      // Use filesystem check since OSS is mounted
      await fs.access(this.getFilesystemPath(key));
      return true;
    } catch {
      return false;
    }
  }

  async delete(key: string): Promise<void> {
    // Delete from OSS using SDK (more reliable than filesystem delete)
    await this.client.delete(key);
  }

  async stat(key: string): Promise<FileMetadata> {
    // Use filesystem stat since OSS is mounted
    const stats = await fs.stat(this.getFilesystemPath(key));
    return {
      size: stats.size,
      mtime: stats.mtime,
    };
  }

  getFilesystemPath(key: string): string {
    // Return mount point path - OSS is accessible as filesystem
    return path.join(this.mountPoint, key);
  }

  async copy(sourceKey: string, destKey: string): Promise<void> {
    // Use OSS copy operation (more efficient than filesystem copy)
    await this.client.copy(destKey, sourceKey);
  }
}
