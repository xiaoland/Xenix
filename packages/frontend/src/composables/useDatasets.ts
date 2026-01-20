/**
 * Datasets Composable
 * Uses TanStack Query with Hono RPC client for type-safe data fetching
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { MaybeRef, unref } from "vue";

import { client } from "../api/client";

export function useDatasets() {
  return useQuery({
    queryKey: ["datasets"],
    queryFn: async () => {
      const response = await client.data.$get({});
      if (!response.ok) {
        throw new Error("Failed to fetch datasets");
      }
      return response.json();
    },
  });
}

export function useDataset(id?: MaybeRef<number | string | undefined>) {
  return useQuery({
    queryKey: ["dataset", id],
    queryFn: async () => {
      const response = await client.data[":id"].$get({
        param: { id: String(unref(id)) },
      });
      if (!response.ok) {
        throw new Error("Failed to fetch dataset");
      }
      return response.json();
    },
    enabled: !!unref(id),
  });
}

export function useUploadDataset() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (params: {
      file: File;
      name: string;
      projectId: number;
    }) => {
      // Generate simple OSS key with UUID
      const uuid = crypto.randomUUID();
      const key = `datasets/${uuid}`;

      // Step 1: Get presigned URL
      const presignedResponse = await client.data["upload-url"].$post({
        json: {
          key,
          contentType: params.file.type,
        },
      });

      if (!presignedResponse.ok) {
        const error = await presignedResponse.json();
        throw new Error(error.error || "Failed to get upload URL");
      }

      const presignedData = await presignedResponse.json();

      // Step 2: Upload directly to OSS
      const uploadResponse = await fetch(presignedData.url, {
        method: "PUT",
        headers: {
          "Content-Type": params.file.type,
        },
        body: params.file,
      });

      if (!uploadResponse.ok) {
        throw new Error(`Upload failed: ${uploadResponse.statusText}`);
      }

      // Step 3: Confirm upload to backend
      const confirmResponse = await client.data["confirm-upload"].$post({
        json: {
          key: presignedData.key,
          name: params.name,
          projectId: params.projectId,
          fileName: params.file.name,
          fileSize: params.file.size,
        },
      });

      if (!confirmResponse.ok) {
        const error = await confirmResponse.json();
        throw new Error(error.error || "Failed to confirm upload");
      }

      return confirmResponse.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["datasets"] });
    },
  });
}

export function useDeleteDataset() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: number | string) => {
      const response = await client.data[":id"].$delete({
        param: { id: String(id) },
      });
      if (!response.ok) {
        throw new Error("Failed to delete dataset");
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["datasets"] });
    },
  });
}
