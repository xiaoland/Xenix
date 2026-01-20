import { AwsClient } from "aws4fetch";
import path from "path";
import fs from "fs/promises";
import type { StorageService } from "./StorageService";
import type {
  FileMetadata,
  PresignedUrlRequest,
  PresignedUrlResponse,
  OSSConfig,
} from "./schemas";

/**
 * Aliyun OSS storage implementation using aws4fetch
 * Used for production environment with OSS mounted as filesystem
 */
export class OSSStorage implements StorageService {
  private awsClient: AwsClient;
  private mountPoint: string;
  private endpoint: string;
  private bucket: string;

  constructor(config: OSSConfig, mountPoint = "/mnt/oss") {
    this.awsClient = new AwsClient({
      accessKeyId: config.accessKeyId,
      secretAccessKey: config.accessKeySecret,
      region: config.region || "cn-hangzhou",
      service: "oss",
    });
    this.mountPoint = mountPoint;
    this.endpoint =
      config.endpoint ||
      `https://${config.bucket}.oss-${config.region || "cn-hangzhou"}.aliyuncs.com`;
    this.bucket = config.bucket;
  }

  async generatePresignedUploadUrl(
    request: PresignedUrlRequest,
  ): Promise<PresignedUrlResponse> {
    // Generate presigned PUT URL for direct upload from frontend
    const url = `${this.endpoint}/${request.key}`;

    // Create a signed URL using aws4fetch
    const headers: Record<string, string> = {};
    if (request.contentType) {
      headers["Content-Type"] = request.contentType;
    }
    const signedUrl = await this.awsClient.sign(url, {
      method: "PUT",
      headers,
    });

    const expiresAt = new Date(Date.now() + request.expiresIn * 1000);

    return {
      url: signedUrl.url,
      key: request.key,
      expiresAt,
    };
  }

  async generatePresignedDownloadUrl(
    key: string,
    expiresIn = 3600,
  ): Promise<string> {
    // Generate presigned GET URL for direct download from frontend
    const url = `${this.endpoint}/${key}`;

    const signedUrl = await this.awsClient.sign(url, {
      method: "GET",
    });

    return signedUrl.url;
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
    // Delete from OSS using aws4fetch
    const url = `${this.endpoint}/${key}`;
    await this.awsClient.fetch(url, { method: "DELETE" });
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
    // Use OSS copy operation via aws4fetch
    const url = `${this.endpoint}/${destKey}`;
    await this.awsClient.fetch(url, {
      method: "PUT",
      headers: {
        "x-oss-copy-source": `/${this.bucket}/${sourceKey}`,
      },
    });
  }

  async fetch(key: string, options?: { timeout?: number }): Promise<Response> {
    // Fetch file content from OSS
    const url = `${this.endpoint}/${key}`;
    const fetchOptions: RequestInit = {
      method: "GET",
    };

    if (options?.timeout) {
      fetchOptions.signal = AbortSignal.timeout(options.timeout);
    }

    return this.awsClient.fetch(url, fetchOptions);
  }
}
