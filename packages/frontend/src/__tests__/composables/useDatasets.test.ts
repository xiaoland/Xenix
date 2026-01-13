import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@tanstack/vue-query', () => ({
  useQuery: vi.fn(),
  useMutation: vi.fn(),
  useQueryClient: vi.fn(),
}));

vi.mock('../../api/client', () => ({
  client: {
    data: {
      $get: vi.fn(),
      $post: vi.fn(),
      ':id': {
        $get: vi.fn(),
        $delete: vi.fn(),
      },
    },
  },
}));

describe('useDatasets composable', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('useDatasets', () => {
    it('should be defined', async () => {
      const { useDatasets } = await import('../../composables/useDatasets');
      expect(useDatasets).toBeDefined();
    });
  });

  describe('useDataset', () => {
    it('should be defined', async () => {
      const { useDataset } = await import('../../composables/useDatasets');
      expect(useDataset).toBeDefined();
    });
  });

  describe('useUploadDataset', () => {
    it('should be defined', async () => {
      const { useUploadDataset } = await import('../../composables/useDatasets');
      expect(useUploadDataset).toBeDefined();
    });
  });

  describe('useDeleteDataset', () => {
    it('should be defined', async () => {
      const { useDeleteDataset } = await import('../../composables/useDatasets');
      expect(useDeleteDataset).toBeDefined();
    });
  });
});
