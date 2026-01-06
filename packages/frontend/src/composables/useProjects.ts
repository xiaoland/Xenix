/**
 * Projects Composable
 * Uses TanStack Query with Hono RPC client for type-safe data fetching
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query';
import { client } from '../api/client';

export function useProjects() {
  return useQuery({
    queryKey: ['projects'],
    queryFn: async () => {
      const response = await client.api.projects.$get();
      if (!response.ok) {
        throw new Error('Failed to fetch projects');
      }
      const data = await response.json();
      return data.projects || [];
    },
  });
}

export function useProject(id: number | string) {
  return useQuery({
    queryKey: ['project', id],
    queryFn: async () => {
      const response = await client.api.projects[':id'].$get({
        param: { id: String(id) },
      });
      if (!response.ok) {
        throw new Error('Failed to fetch project');
      }
      const data = await response.json();
      return data.project;
    },
    enabled: !!id,
  });
}

export function useCreateProject() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (project: { name: string; description?: string }) => {
      const response = await client.api.projects.$post({
        json: project,
      });
      if (!response.ok) {
        throw new Error('Failed to create project');
      }
      const data = await response.json();
      return data.project;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
    },
  });
}

export function useUpdateProject() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      id,
      updates,
    }: {
      id: number | string;
      updates: { name?: string; description?: string; status?: 'active' | 'completed' | 'archived' };
    }) => {
      const response = await client.api.projects[':id'].$put({
        param: { id: String(id) },
        json: updates,
      });
      if (!response.ok) {
        throw new Error('Failed to update project');
      }
      const data = await response.json();
      return data.project;
    },
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      queryClient.invalidateQueries({ queryKey: ['project', id] });
    },
  });
}

export function useDeleteProject() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: number | string) => {
      const response = await client.api.projects[':id'].$delete({
        param: { id: String(id) },
      });
      if (!response.ok) {
        throw new Error('Failed to delete project');
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
    },
  });
}
