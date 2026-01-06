/**
 * Work Items Composable
 * Uses TanStack Query with Hono RPC client for type-safe data fetching
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query';
import { client } from '../api/client';
export function useWorkItems() {
    return useQuery({
        queryKey: ['work-items'],
        queryFn: async () => {
            const response = await client.api['work-items'].$get();
            if (!response.ok) {
                throw new Error('Failed to fetch work items');
            }
            const data = await response.json();
            return data.workItems || [];
        },
    });
}
export function useWorkItem(id) {
    return useQuery({
        queryKey: ['work-item', id],
        queryFn: async () => {
            const response = await client.api['work-items'][':id'].$get({
                param: { id: String(id) },
            });
            if (!response.ok) {
                throw new Error('Failed to fetch work item');
            }
            const data = await response.json();
            return data.workItem;
        },
        enabled: !!id,
    });
}
export function useCreateWorkItem() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (workItem) => {
            const response = await client.api['work-items'].$post({
                json: workItem,
            });
            if (!response.ok) {
                throw new Error('Failed to create work item');
            }
            const data = await response.json();
            return data.workItem;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['work-items'] });
            queryClient.invalidateQueries({ queryKey: ['projects'] });
        },
    });
}
export function useUpdateWorkItem() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async ({ id, updates, }) => {
            const response = await client.api['work-items'][':id'].$put({
                param: { id: String(id) },
                json: updates,
            });
            if (!response.ok) {
                throw new Error('Failed to update work item');
            }
            const data = await response.json();
            return data.workItem;
        },
        onSuccess: (_, { id }) => {
            queryClient.invalidateQueries({ queryKey: ['work-items'] });
            queryClient.invalidateQueries({ queryKey: ['work-item', id] });
        },
    });
}
export function useDeleteWorkItem() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (id) => {
            const response = await client.api['work-items'][':id'].$delete({
                param: { id: String(id) },
            });
            if (!response.ok) {
                throw new Error('Failed to delete work item');
            }
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['work-items'] });
        },
    });
}
