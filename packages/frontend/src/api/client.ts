/**
 * Hono RPC Client
 * Type-safe API client using Hono's RPC functionality with authentication
 */
import { hc } from 'hono/client';

import type { AppType } from '@xenix/backend';

import { API_CONFIG } from '../constants/config';

const apiUrl = import.meta.env.VITE_API_URL || API_CONFIG.DEFAULT_URL;

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
