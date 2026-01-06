/**
 * Dataset Service
 * Business logic for dataset operations
 */

import { DatasetRepository } from '../repositories/index.js';
import { NotFoundError } from '../errors/index.js';

export class DatasetService {
  private datasetRepo: DatasetRepository;

  constructor() {
    this.datasetRepo = new DatasetRepository();
  }

  async getAllDatasets() {
    return await this.datasetRepo.findAll();
  }

  async getDatasetById(id: number) {
    const dataset = await this.datasetRepo.findById(id);

    if (!dataset) {
      throw new NotFoundError('Dataset');
    }

    return dataset;
  }

  async createDataset(data: any) {
    return await this.datasetRepo.create(data);
  }

  async deleteDataset(id: number) {
    const dataset = await this.datasetRepo.findById(id);

    if (!dataset) {
      throw new NotFoundError('Dataset');
    }

    await this.datasetRepo.delete(id);
    return dataset;
  }
}
