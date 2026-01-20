import fs from 'fs/promises';
import path from 'path';
import type { StorageService } from './StorageService';
import type {
  FileMetadata,
  PresignedUrlRequest,
  PresignedUrlResponse,
} from './schemas';

/**
 * Local filesystem storage implementation
 * Used for development environment
 */
export class LocalStorage implements StorageService {
  constructor(private basePath: string) {}

  async generatePresignedUploadUrl(
    request: PresignedUrlRequest
  ): Promise<PresignedUrlResponse> {
    // For local dev, return a fake "presigned URL" that points to backend
    // Frontend will actually POST to backend's upload endpoint
    const expiresAt = new Date(Date.now() + request.expiresIn * 1000);

    return {
      url: `http://localhost:3000/upload/local/${encodeURIComponent(request.key)}`,
      key: request.key,
      expiresAt,
    };
  }

  async generatePresignedDownloadUrl(
    key: string,
    expiresIn = 3600
  ): Promise<string> {
    // For local dev, return a URL that points to backend's download endpoint
    return `http://localhost:3000/download/${encodeURIComponent(key)}`;
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
    // For local storage, read file from filesystem and return as Response
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
}
