import fs from 'fs/promises';
import path from 'path';
import type { StorageService } from './StorageService';
import type {
  FileMetadata,
  PresignedUrlRequest,
  PresignedUrlResponse,
} from './schemas';

/**
 * Unified filesystem storage implementation
 * Works with both local filesystem (development) and mounted OSS bucket (production)
 * Base path is configurable via STORAGE_BASE_PATH environment variable
 */
export class FileSystemStorage implements StorageService {
  constructor(private basePath: string) {}

  async generatePresignedUploadUrl(
    request: PresignedUrlRequest
  ): Promise<PresignedUrlResponse> {
    // For filesystem storage, return backend upload endpoint
    // Frontend will POST to backend which saves to filesystem
    const expiresAt = new Date(Date.now() + request.expiresIn * 1000);

    return {
      url: `/upload/${encodeURIComponent(request.key)}`,
      key: request.key,
      expiresAt,
    };
  }

  async generatePresignedDownloadUrl(
    key: string,
    expiresIn = 3600
  ): Promise<string> {
    // Return backend download endpoint
    return `/download/${encodeURIComponent(key)}`;
  }

  async exists(key: string): Promise<boolean> {
    try {
      await fs.access(this.getFilesystemPath(key));
      return true;
    } catch {
      return false;
    }
  }

  async delete(key: string): Promise<void> {
    await fs.unlink(this.getFilesystemPath(key));
  }

  async stat(key: string): Promise<FileMetadata> {
    const stats = await fs.stat(this.getFilesystemPath(key));
    return {
      size: stats.size,
      mtime: stats.mtime,
    };
  }

  getFilesystemPath(key: string): string {
    return path.join(this.basePath, key);
  }

  async copy(sourceKey: string, destKey: string): Promise<void> {
    const sourcePath = this.getFilesystemPath(sourceKey);
    const destPath = this.getFilesystemPath(destKey);

    // Ensure destination directory exists
    await fs.mkdir(path.dirname(destPath), { recursive: true });

    // Copy file
    await fs.copyFile(sourcePath, destPath);
  }

  async fetch(key: string, options?: { timeout?: number }): Promise<Response> {
    // Read file from filesystem and return as Response
    const filePath = this.getFilesystemPath(key);

    try {
      const content = await fs.readFile(filePath, 'utf-8');
      return new Response(content, {
        status: 200,
        headers: {
          'Content-Type': 'application/json',
        },
      });
    } catch (error: any) {
      if (error.code === 'ENOENT') {
        return new Response(null, { status: 404 });
      }
      throw error;
    }
  }

  async upload(key: string, buffer: ArrayBuffer, contentType?: string): Promise<void> {
    const filePath = this.getFilesystemPath(key);

    // Ensure directory exists
    await fs.mkdir(path.dirname(filePath), { recursive: true });

    // Write buffer to filesystem
    await fs.writeFile(filePath, Buffer.from(buffer));
  }
}
