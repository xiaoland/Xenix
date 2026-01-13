import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@tanstack/vue-query', () => ({
  useQuery: vi.fn(),
  useMutation: vi.fn(),
  useQueryClient: vi.fn(),
}));

vi.mock('../../api/client', () => ({
  client: {
    'work-items': {
      $get: vi.fn(),
      $post: vi.fn(),
      ':id': {
        $get: vi.fn(),
        $put: vi.fn(),
        $delete: vi.fn(),
      },
    },
  },
}));

describe('useWorkItems composable', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('useWorkItems', () => {
    it('should be defined', async () => {
      const { useWorkItems } = await import('../../composables/useWorkItems');
      expect(useWorkItems).toBeDefined();
    });
  });

  describe('useWorkItem', () => {
    it('should be defined', async () => {
      const { useWorkItem } = await import('../../composables/useWorkItems');
      expect(useWorkItem).toBeDefined();
    });
  });

  describe('useCreateWorkItem', () => {
    it('should be defined', async () => {
      const { useCreateWorkItem } = await import('../../composables/useWorkItems');
      expect(useCreateWorkItem).toBeDefined();
    });
  });

  describe('useUpdateWorkItem', () => {
    it('should be defined', async () => {
      const { useUpdateWorkItem } = await import('../../composables/useWorkItems');
      expect(useUpdateWorkItem).toBeDefined();
    });
  });

  describe('useDeleteWorkItem', () => {
    it('should be defined', async () => {
      const { useDeleteWorkItem } = await import('../../composables/useWorkItems');
      expect(useDeleteWorkItem).toBeDefined();
    });
  });
});
