/**
 * ML Backend Deployments Queries
 * TanStack Query hooks for ML backend deployment data
 */
import { useQuery } from "@tanstack/vue-query";

import type { MLBackendDeployment } from "@xenix/shared";
import { client } from "@/services/api-client";

export function useMLBackendDeployments() {
  return useQuery({
    queryKey: ["ml-backend-deployments"],
    queryFn: async (): Promise<MLBackendDeployment[]> => {
      const response = await client["ml-backend-deployments"].$get({});
      if (!response.ok) {
        throw new Error("Failed to fetch ML backend deployments");
      }
      return response.json() as Promise<MLBackendDeployment[]>;
    },
  });
}
