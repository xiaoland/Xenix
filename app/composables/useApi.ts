/**
 * API Composable
 * Provides a configured $fetch instance with authentication and error handling
 */

import { navigateTo, useRuntimeConfig } from "#app";
import { useAuth } from "./useAuth";

export function useApi() {
  const config = useRuntimeConfig();
  const { token } = useAuth();

  return $fetch.create({
    baseURL: config.public.apiBase || "https://api.example.com",

    onRequest({ options }) {
      // Add Authorization header if token exists
      if (token.value) {
        options.headers = options.headers || {};
        // @ts-ignore
        options.headers.Authorization = `Bearer ${token.value}`;
      }
    },

    // Handle 401 errors by redirecting to signin
    async onResponseError({ response }) {
      if (response.status === 401) {
        // If on client, save intended route
        if (import.meta.client) {
          sessionStorage.setItem("intendedRoute", window.location.pathname);
        }
        await navigateTo("/signin");
      }
    },
  });
}
