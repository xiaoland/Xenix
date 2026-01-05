/**
 * Hono RPC Client
 * Type-safe API client using Hono's RPC functionality
 */

import { hc } from 'hono/client';
import type { AppType } from '@xenix/backend';

const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:3000';

export const client = hc<AppType>(apiUrl);

export type Client = typeof client;
