/**
 * Datasets Composable
 * Uses TanStack Query with Hono RPC client for type-safe data fetching
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query';
import { client } from '../api/client';
export function useDatasets() {
    return useQuery({
        queryKey: ['datasets'],
        queryFn: async () => {
            const response = await client.api.data.$get();
            if (!response.ok) {
                throw new Error('Failed to fetch datasets');
            }
            const data = await response.json();
            return data.datasets || [];
        },
    });
}
export function useDataset(id) {
    return useQuery({
        queryKey: ['dataset', id],
        queryFn: async () => {
            const response = await client.api.data[':id'].$get({
                param: { id: String(id) },
            });
            if (!response.ok) {
                throw new Error('Failed to fetch dataset');
            }
            const data = await response.json();
            return data.dataset;
        },
        enabled: !!id,
    });
}
export function useUploadDataset() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (formData) => {
            const response = await client.api.data.$post({
                body: formData,
            });
            if (!response.ok) {
                throw new Error('Failed to upload dataset');
            }
            const data = await response.json();
            return data.dataset;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['datasets'] });
        },
    });
}
export function useDeleteDataset() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (id) => {
            const response = await client.api.data[':id'].$delete({
                param: { id: String(id) },
            });
            if (!response.ok) {
                throw new Error('Failed to delete dataset');
            }
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['datasets'] });
        },
    });
}
