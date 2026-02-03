/**
 * Query Layer Guidelines
 *
 * This module provides utilities and best practices for using TanStack Query.
 *
 * ## Guidelines
 *
 * 1. **Query Keys**: Use descriptive, hierarchical keys
 *    - ['projects'] - All projects
 *    - ['project', id] - Single project
 *    - ['tasks', { workItemId, type }] - Filtered tasks
 *
 * 2. **Error Handling**: Always handle errors consistently
 *    - Use the error state components for UI errors
 *    - Log errors for debugging
 *
 * 3. **Loading States**: Show appropriate loading feedback
 *    - Use LoadingState component for full-page loads
 *    - Use skeleton screens for partial content
 *
 * 4. **Caching**: Configure cache times appropriately
 *    - Short cache (0-1 min): Real-time data
 *    - Medium cache (5 min): User data
 *    - Long cache (1 hour+): Reference data
 *
 * 5. **Optimistic Updates**: Use for better UX
 *    - Only for low-risk operations
 *    - Always handle rollback on error
 */

import type { QueryClientConfig, QueryKey } from "@tanstack/vue-query";

/**
 * Default query client configuration
 */
export const defaultQueryClientConfig: QueryClientConfig = {
  defaultOptions: {
    queries: {
      // Data is considered fresh for 5 minutes
      staleTime: 1000 * 60 * 5,
      // Keep data in cache for 10 minutes after last use
      gcTime: 1000 * 60 * 10,
      // Retry failed queries 3 times
      retry: 3,
      // Don't retry on 404 errors
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
      // Refetch on window focus (disable for development)
      refetchOnWindowFocus: import.meta.env.PROD,
      // Refetch on reconnect
      refetchOnReconnect: true,
    },
    mutations: {
      // Retry mutations only once
      retry: 1,
    },
  },
};

/**
 * Query key factory helpers
 */
export const queryKeys = {
  // Auth
  auth: {
    all: ["auth"] as const,
    user: () => [...queryKeys.auth.all, "user"] as const,
  },

  // Projects
  projects: {
    all: ["projects"] as const,
    list: () => [...queryKeys.projects.all] as const,
    detail: (id: string | number) => [...queryKeys.projects.all, id] as const,
  },

  // Work Items
  workItems: {
    all: ["work-items"] as const,
    list: (projectId?: string | number) =>
      projectId
        ? [...queryKeys.workItems.all, { projectId }]
        : ([...queryKeys.workItems.all] as const),
    detail: (id: string | number) => [...queryKeys.workItems.all, id] as const,
  },

  // Datasets
  datasets: {
    all: ["datasets"] as const,
    list: () => [...queryKeys.datasets.all] as const,
    detail: (id: string | number) => [...queryKeys.datasets.all, id] as const,
    preview: (id: string | number) =>
      [...queryKeys.datasets.all, id, "preview"] as const,
    columns: (id: string | number) =>
      [...queryKeys.datasets.all, id, "columns"] as const,
  },

  // Tasks
  tasks: {
    all: ["tasks"] as const,
    list: (filters?: { workItemId?: string; type?: string }) =>
      filters
        ? [...queryKeys.tasks.all, { filters }]
        : ([...queryKeys.tasks.all] as const),
    detail: (id: string | number) => [...queryKeys.tasks.all, id] as const,
    logs: (id: string | number) =>
      [...queryKeys.tasks.all, id, "logs"] as const,
  },

  // ML
  ml: {
    models: {
      all: ["models"] as const,
      list: () => [...queryKeys.ml.models.all] as const,
      detail: (id: string | number) =>
        [...queryKeys.ml.models.all, id] as const,
    },
    backends: {
      all: ["ml-backends"] as const,
      list: () => [...queryKeys.ml.backends.all] as const,
    },
    tuning: {
      all: ["tuning"] as const,
      detail: (id: string | number) =>
        [...queryKeys.ml.tuning.all, id] as const,
    },
    prediction: {
      all: ["prediction"] as const,
      detail: (id: string | number) =>
        [...queryKeys.ml.prediction.all, id] as const,
    },
  },
};

/**
 * Type-safe query key builder
 */
export function buildQueryKey(
  base: string,
  ...segments: (string | number | Record<string, unknown> | undefined)[]
): QueryKey {
  return [base, ...segments.filter(Boolean)];
}

/**
 * Cache time presets (in milliseconds)
 */
export const cacheTime = {
  /** Real-time data - no caching */
  realtime: 0,
  /** Short term - 1 minute */
  short: 1000 * 60,
  /** Medium term - 5 minutes */
  medium: 1000 * 60 * 5,
  /** Long term - 1 hour */
  long: 1000 * 60 * 60,
  /** Permanent - 24 hours */
  permanent: 1000 * 60 * 60 * 24,
};

/**
 * Standardized error handler for queries
 */
export function handleQueryError(error: unknown): Error {
  if (error instanceof Error) {
    return error;
  }

  if (typeof error === "string") {
    return new Error(error);
  }

  return new Error("An unknown error occurred");
}

/**
 * Extract error message from API response
 */
export function extractErrorMessage(data: unknown): string {
  if (typeof data === "object" && data !== null) {
    const err = data as { error?: string; message?: string };
    return err.error || err.message || "Unknown error";
  }
  return "Unknown error";
}
