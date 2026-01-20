/**
 * Dataset Service
 * Business logic for dataset operations
 */
import { NotFoundError } from "../errors";
import { DatasetRepository } from "../repositories";
import logger from "../utils/logger";

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
      throw new NotFoundError("Dataset");
    }

    return dataset;
  }

  async createDatasetFromOSSKey(params: {
    key: string;
    name: string;
    description: string | null;
    projectId: number | null;
    fileName: string;
    fileSize: number;
    columns: string[];
    rowCount: number;
  }) {
    // Create dataset record with the OSS key as filePath
    return await this.datasetRepo.create({
      projectId: params.projectId && !isNaN(params.projectId) ? params.projectId : null,
      name: params.name,
      description: params.description,
      filePath: params.key, // Store OSS key directly
      fileName: params.fileName,
      fileSize: params.fileSize,
      columns: params.columns,
      rowCount: params.rowCount,
    });
  }

  async deleteDataset(id: number) {
    const dataset = await this.datasetRepo.findById(id);

    if (!dataset) {
      throw new NotFoundError("Dataset");
    }

    // Note: File deletion from OSS should be handled separately
    // For now, we just delete the database record
    // TODO: Implement OSS file deletion via storage service

    // Delete dataset record
    await this.datasetRepo.delete(id);
    return dataset;
  }
}
