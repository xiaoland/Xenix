import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ModelService } from '../../services/ModelService';
import { NotFoundError } from '../../errors';

vi.mock('../../database', () => ({
  db: {
    select: vi.fn(),
  },
  schema: {
    modelMetadata: {},
  },
}));

vi.mock('../../utils/syncModels');

describe('ModelService', () => {
  let modelService: ModelService;

  beforeEach(() => {
    vi.clearAllMocks();
    modelService = new ModelService();
  });

  describe('getModelByName', () => {
    it('should throw NotFoundError when model does not exist', async () => {
      const { db } = await import('../../database');
      const dbMock = db as any;

      dbMock.select.mockReturnValue({
        from: vi.fn().mockReturnValue({
          where: vi.fn().mockReturnValue({
            limit: vi.fn().mockResolvedValue([]),
          }),
        }),
      });

      await expect(
        modelService.getModelByName('nonexistent-model')
      ).rejects.toThrow(NotFoundError);
    });
  });
});
