/**
 * Projects Queries
 * TanStack Query hooks for project data fetching
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";

import { client } from "@/services/api-client";

export function useProjects() {
  return useQuery({
    queryKey: ["projects"],
    queryFn: async () => {
      const response = await client.projects.$get({});
      if (!response.ok) {
        const error = (await response.json()) as any;
        throw new Error(error.error || "Failed to fetch projects");
      }
      return response.json();
    },
  });
}

export function useProject(id: number | string) {
  return useQuery({
    queryKey: ["project", id],
    queryFn: async () => {
      const response = await client.projects[":id"].$get({
        param: { id: String(id) },
      });
      if (!response.ok) {
        const error = (await response.json()) as any;
        throw new Error(error.error || "Failed to fetch project");
      }
      return response.json();
    },
    enabled: !!id,
  });
}

export function useCreateProject() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (project: { name: string; description?: string }) => {
      const response = await client.projects.$post({
        json: project,
      });
      if (!response.ok) {
        const error = (await response.json()) as any;
        throw new Error(error.error || "Failed to create project");
      }
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
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
      updates: {
        name?: string;
        description?: string;
        status?: "active" | "completed" | "archived";
      };
    }) => {
      const response = await client.projects[":id"].$put({
        param: { id: String(id) },
        json: updates,
      });
      if (!response.ok) {
        const error = (await response.json()) as any;
        throw new Error(error.error || "Failed to update project");
      }
      return response.json();
    },
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      queryClient.invalidateQueries({ queryKey: ["project", id] });
    },
  });
}

export function useDeleteProject() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: number | string) => {
      const response = await client.projects[":id"].$delete({
        param: { id: String(id) },
      });
      if (!response.ok) {
        const error = (await response.json()) as any;
        throw new Error(error.error || "Failed to delete project");
      }
      return null;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });
}
