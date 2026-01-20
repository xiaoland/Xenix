/**
 * Dataset Service
 * Business logic for dataset operations
 */
import { randomUUID } from "crypto";
import fs from "fs/promises";
import path from "path";

import { NotFoundError } from "../errors";
import { DatasetRepository } from "../repositories";
import { analyzeExcelFile } from "../utils/datasetUtils";
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
      projectId:
        params.projectId && !isNaN(params.projectId) ? params.projectId : null,
      name: params.name,
      description: params.description,
      filePath: params.key, // Store OSS key directly
      fileName: params.fileName,
      fileSize: params.fileSize,
      columns: params.columns,
      rowCount: params.rowCount,
    });
  }

  async createDataset(
    file: File,
    name: string,
    description: string | null,
    projectId: number | null,
    datasetsDir: string,
  ) {
    const fileId = randomUUID();
    const filePath = path.join(datasetsDir, fileId, file.name);

    // Ensure directory exists
    await fs.mkdir(path.dirname(filePath), { recursive: true });

    // Save file
    const buffer = await file.arrayBuffer();
    await fs.writeFile(filePath, Buffer.from(buffer));

    // Analyze the Excel file
    const { columns, rowCount } = await analyzeExcelFile(filePath);

    // Create dataset record
    return await this.datasetRepo.create({
      projectId: projectId && !isNaN(projectId) ? projectId : null,
      name,
      description,
      filePath: `datasets/${fileId}/${file.name}`,
      fileName: file.name,
      fileSize: file.size,
      columns,
      rowCount,
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
