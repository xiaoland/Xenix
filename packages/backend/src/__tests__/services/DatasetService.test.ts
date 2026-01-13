import { beforeEach, describe, expect, it, vi } from 'vitest';

import { DatasetService } from '../../services/DatasetService';
import { NotFoundError } from '../../errors';
import { DatasetRepository } from '../../repositories/DatasetRepository';

vi.mock('../../repositories/DatasetRepository');
vi.mock('../../utils/datasetUtils');
vi.mock('../../utils/taskUtils');
vi.mock('fs/promises');

describe('DatasetService', () => {
  let datasetService: DatasetService;
  let mockDatasetRepo: any;

  beforeEach(() => {
    vi.clearAllMocks();
    datasetService = new DatasetService();
    mockDatasetRepo = (datasetService as any).datasetRepo;
  });

  describe('getAllDatasets', () => {
    it('should return all datasets', async () => {
      const mockDatasets = [
        { id: 1, name: 'Dataset 1', filePath: '/path/to/file1' },
        { id: 2, name: 'Dataset 2', filePath: '/path/to/file2' },
      ];
      mockDatasetRepo.findAll = vi.fn().mockResolvedValue(mockDatasets);

      const result = await datasetService.getAllDatasets();

      expect(result).toEqual(mockDatasets);
      expect(mockDatasetRepo.findAll).toHaveBeenCalled();
    });
  });

  describe('getDatasetById', () => {
    it('should return a dataset when found', async () => {
      const mockDataset = {
        id: 1,
        name: 'Test Dataset',
        filePath: '/path/to/file',
      };
      mockDatasetRepo.findById = vi.fn().mockResolvedValue(mockDataset);

      const result = await datasetService.getDatasetById(1);

      expect(result).toEqual(mockDataset);
      expect(mockDatasetRepo.findById).toHaveBeenCalledWith(1);
    });

    it('should throw NotFoundError when dataset does not exist', async () => {
      mockDatasetRepo.findById = vi.fn().mockResolvedValue(null);

      await expect(datasetService.getDatasetById(999)).rejects.toThrow(
        NotFoundError
      );
    });
  });

  describe('deleteDataset', () => {
    it('should throw NotFoundError when dataset does not exist', async () => {
      mockDatasetRepo.findById = vi.fn().mockResolvedValue(null);

      await expect(datasetService.deleteDataset(999)).rejects.toThrow(
        NotFoundError
      );
    });
  });
});
