import { AwsClient } from "aws4fetch";
import OSS from "ali-oss";
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
  private ossClient: OSS;
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

    // Initialize native OSS client for direct uploads
    this.ossClient = new OSS({
      region: config.region || "cn-hangzhou",
      accessKeyId: config.accessKeyId,
      accessKeySecret: config.accessKeySecret,
      bucket: config.bucket,
      secure: true, // Use HTTPS
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
    // Add X-Amz-Expires query parameter before signing (required by OSS)
    const url = `${this.endpoint}/${request.key}?X-Amz-Expires=${request.expiresIn}`;

    // Create a signed URL using aws4fetch
    // Note: For presigned URLs, we only sign headers that will be sent by the client
    const headers: Record<string, string> = {};
    if (request.contentType) {
      headers["Content-Type"] = request.contentType;
    }

    const signedUrl = await this.awsClient.sign(url, {
      method: "PUT",
      headers,
      aws: {
        signQuery: true, // Sign query string instead of Authorization header for presigned URLs
      },
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

  async upload(key: string, buffer: ArrayBuffer, contentType?: string): Promise<void> {
    // Upload file buffer directly to OSS using native SDK
    // Convert ArrayBuffer to Buffer
    const bodyBuffer = Buffer.from(buffer);

    try {
      const options: OSS.PutObjectOptions = {};
      if (contentType) {
        options.headers = {
          "Content-Type": contentType,
        };
      }

      await this.ossClient.put(key, bodyBuffer, options);
    } catch (error: any) {
      throw new Error(`OSS upload failed: ${error.message || error}`);
    }
  }
}
