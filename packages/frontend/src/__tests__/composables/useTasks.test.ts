import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@tanstack/vue-query', () => ({
  useQuery: vi.fn(),
  useQueryClient: vi.fn(),
}));

vi.mock('../../api/client', () => ({
  client: {
    tasks: {
      $get: vi.fn(),
      ':id': {
        $get: vi.fn(),
      },
    },
  },
}));

describe('useTasks composable', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('useTasks', () => {
    it('should be defined', async () => {
      const { useTasks } = await import('../../composables/useTasks');
      expect(useTasks).toBeDefined();
    });
  });

  describe('useTask', () => {
    it('should be defined', async () => {
      const { useTask } = await import('../../composables/useTasks');
      expect(useTask).toBeDefined();
    });
  });
});
