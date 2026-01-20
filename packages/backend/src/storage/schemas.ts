import { z } from 'zod';

// OSS configuration schema
export const ossConfigSchema = z.object({
  region: z.string(),
  accessKeyId: z.string(),
  accessKeySecret: z.string(),
  bucket: z.string(),
  endpoint: z.string().optional(),
});

export type OSSConfig = z.infer<typeof ossConfigSchema>;

// Storage operation results
export const fileMetadataSchema = z.object({
  size: z.number(),
  mtime: z.date(),
  contentType: z.string().optional(),
});

export type FileMetadata = z.infer<typeof fileMetadataSchema>;

// Presigned URL request
export const presignedUrlRequestSchema = z.object({
  key: z.string(),
  expiresIn: z.number().default(3600), // 1 hour
  contentType: z.string().optional(),
});

export type PresignedUrlRequest = z.infer<typeof presignedUrlRequestSchema>;

// Presigned URL response
export const presignedUrlResponseSchema = z.object({
  url: z.string().url(),
  key: z.string(),
  expiresAt: z.date(),
});

export type PresignedUrlResponse = z.infer<typeof presignedUrlResponseSchema>;
