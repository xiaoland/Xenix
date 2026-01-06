/**
 * Hono RPC Client
 * Type-safe API client using Hono's RPC functionality with authentication
 */
import { hc } from 'hono/client';

import type { AppType } from '@xenix/backend';

const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:3000';

// Create client with authentication headers
export const client = hc<AppType>(apiUrl, {
  headers: () => {
    const token = localStorage.getItem('auth_token');
    return token
      ? { Authorization: `Bearer ${token}` }
      : ({} as Record<string, string>);
  },
});

export type Client = typeof client;
