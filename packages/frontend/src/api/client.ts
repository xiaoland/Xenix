/**
 * Hono RPC Client
 * Type-safe API client using Hono's RPC functionality with authentication
 */
import { hc } from 'hono/client';

import type { AppType } from '@xenix/backend';

import { API_CONFIG } from '../constants/config';

const apiUrl = import.meta.env.VITE_API_URL || API_CONFIG.DEFAULT_URL;

/**
 * Custom fetch wrapper that handles 401 unauthorized responses
 * by logging out the user and redirecting to signin
 */
const fetchWithAuth: typeof fetch = async (input, init) => {
  const response = await fetch(input, init);

  // Handle 401 Unauthorized - auto logout
  if (response.status === 401) {
    // Clear authentication data
    localStorage.removeItem('auth_token');
    localStorage.removeItem('auth_user');

    // Redirect to signin page
    if (typeof window !== 'undefined' && window.location.pathname !== '/auth/signin') {
      window.location.href = '/auth/signin';
    }
  }

  return response;
};

// Create client with authentication headers and custom fetch
export const client = hc<AppType>(apiUrl, {
  headers: () => {
    const token = localStorage.getItem('auth_token');
    return token
      ? { Authorization: `Bearer ${token}` }
      : ({} as Record<string, string>);
  },
  fetch: fetchWithAuth,
});

export type Client = typeof client;
