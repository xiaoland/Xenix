import { z } from 'zod';

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
