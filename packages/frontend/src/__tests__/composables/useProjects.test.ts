import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useQueryClient } from '@tanstack/vue-query';

vi.mock('@tanstack/vue-query', () => ({
  useQuery: vi.fn(),
  useMutation: vi.fn(),
  useQueryClient: vi.fn(),
}));

vi.mock('../../api/client', () => ({
  client: {
    projects: {
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

describe('useProjects composable', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('useProjects', () => {
    it('should be defined', async () => {
      const { useProjects } = await import('../../composables/useProjects');
      expect(useProjects).toBeDefined();
    });
  });

  describe('useProject', () => {
    it('should be defined', async () => {
      const { useProject } = await import('../../composables/useProjects');
      expect(useProject).toBeDefined();
    });
  });

  describe('useCreateProject', () => {
    it('should be defined', async () => {
      const { useCreateProject } = await import('../../composables/useProjects');
      expect(useCreateProject).toBeDefined();
    });
  });

  describe('useUpdateProject', () => {
    it('should be defined', async () => {
      const { useUpdateProject } = await import('../../composables/useProjects');
      expect(useUpdateProject).toBeDefined();
    });
  });

  describe('useDeleteProject', () => {
    it('should be defined', async () => {
      const { useDeleteProject } = await import('../../composables/useProjects');
      expect(useDeleteProject).toBeDefined();
    });
  });
});
