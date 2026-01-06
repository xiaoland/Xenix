/**
 * Hono RPC Client
 * Type-safe API client using Hono's RPC functionality with authentication
 */
import { hc } from 'hono/client';
const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:3000';
// Create client with authentication headers
export const client = hc(apiUrl, {
    headers: () => {
        const token = localStorage.getItem('auth_token');
        return token ? { Authorization: `Bearer ${token}` } : {};
    },
});
