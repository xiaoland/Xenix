/**
 * Projects Composable
 * Uses TanStack Query for data fetching and caching
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query';
import { useAuthStore } from '../stores/auth';
import type { Project } from '@xenix/shared';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:3000';

export function useProjects() {
  const authStore = useAuthStore();

  return useQuery({
    queryKey: ['projects'],
    queryFn: async (): Promise<Project[]> => {
      const response = await fetch(`${API_URL}/api/projects`, {
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authStore.token}`,
        },
      });

      if (!response.ok) {
        if (response.status === 401) {
          authStore.logout();
        }
        throw new Error('Failed to fetch projects');
      }

      const data = await response.json();
      return data.projects || [];
    },
    enabled: authStore.isAuthenticated,
  });
}

export function useProject(id: number | string) {
  const authStore = useAuthStore();

  return useQuery({
    queryKey: ['project', id],
    queryFn: async (): Promise<Project> => {
      const response = await fetch(`${API_URL}/api/projects/${id}`, {
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authStore.token}`,
        },
      });

      if (!response.ok) {
        if (response.status === 401) {
          authStore.logout();
        }
        throw new Error('Failed to fetch project');
      }

      const data = await response.json();
      return data.project;
    },
    enabled: authStore.isAuthenticated && !!id,
  });
}

export function useCreateProject() {
  const authStore = useAuthStore();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (project: { name: string; description?: string }): Promise<Project> => {
      const response = await fetch(`${API_URL}/api/projects`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authStore.token}`,
        },
        body: JSON.stringify(project),
      });

      if (!response.ok) {
        if (response.status === 401) {
          authStore.logout();
        }
        throw new Error('Failed to create project');
      }

      const data = await response.json();
      return data.project;
    },
    onSuccess: () => {
      // Invalidate projects query to refetch the list
      queryClient.invalidateQueries({ queryKey: ['projects'] });
    },
  });
}

export function useUpdateProject() {
  const authStore = useAuthStore();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      id,
      updates,
    }: {
      id: number | string;
      updates: { name?: string; description?: string; status?: 'active' | 'completed' | 'archived' };
    }): Promise<Project> => {
      const response = await fetch(`${API_URL}/api/projects/${id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authStore.token}`,
        },
        body: JSON.stringify(updates),
      });

      if (!response.ok) {
        if (response.status === 401) {
          authStore.logout();
        }
        throw new Error('Failed to update project');
      }

      const data = await response.json();
      return data.project;
    },
    onSuccess: (_, { id }) => {
      // Invalidate both list and single project queries
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      queryClient.invalidateQueries({ queryKey: ['project', id] });
    },
  });
}

export function useDeleteProject() {
  const authStore = useAuthStore();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: number | string): Promise<void> => {
      const response = await fetch(`${API_URL}/api/projects/${id}`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authStore.token}`,
        },
      });

      if (!response.ok) {
        if (response.status === 401) {
          authStore.logout();
        }
        throw new Error('Failed to delete project');
      }
    },
    onSuccess: () => {
      // Invalidate projects query to refetch the list
      queryClient.invalidateQueries({ queryKey: ['projects'] });
    },
  });
}
