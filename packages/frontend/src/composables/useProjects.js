/**
 * Projects Composable
 * Uses TanStack Query with Hono RPC client for type-safe data fetching
 * HTTP Semantics Pattern: Success responses return data directly, errors have {code, error}
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query';
import { client } from '../api/client';
export function useProjects() {
    return useQuery({
        queryKey: ['projects'],
        queryFn: async () => {
            const response = await client.api.projects.$get();
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Failed to fetch projects');
            }
            // HTTP semantics: success response is the data directly (array of projects)
            return await response.json();
        },
    });
}
export function useProject(id) {
    return useQuery({
        queryKey: ['project', id],
        queryFn: async () => {
            const response = await client.api.projects[':id'].$get({
                param: { id: String(id) },
            });
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Failed to fetch project');
            }
            // HTTP semantics: success response is the project object directly
            return await response.json();
        },
        enabled: !!id,
    });
}
export function useCreateProject() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (project) => {
            const response = await client.api.projects.$post({
                json: project,
            });
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Failed to create project');
            }
            // HTTP semantics: success response is the created project directly
            return await response.json();
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['projects'] });
        },
    });
}
export function useUpdateProject() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async ({ id, updates, }) => {
            const response = await client.api.projects[':id'].$put({
                param: { id: String(id) },
                json: updates,
            });
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Failed to update project');
            }
            // HTTP semantics: success response is the updated project directly
            return await response.json();
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
        mutationFn: async (id) => {
            const response = await client.api.projects[':id'].$delete({
                param: { id: String(id) },
            });
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Failed to delete project');
            }
            // HTTP semantics: DELETE returns 204 No Content (no body)
            return null;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['projects'] });
        },
    });
}
