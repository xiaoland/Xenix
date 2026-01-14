/**
 * Dataset Service
 * Business logic for dataset operations
 */
import fs from "fs/promises";

import { NotFoundError } from "../errors";
import { DatasetRepository } from "../repositories";
import { analyzeExcelFile } from "../utils/datasetUtils";
import logger from "../utils/logger";
import { saveUploadedFile, validateExcelFile } from "../utils/taskUtils";

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

  async createDataset(
    file: File,
    name: string,
    description: string | null,
    projectId: number | null,
    datasetsDir: string
  ) {
    // Validate file
    if (!validateExcelFile(file.name)) {
      throw new Error(
        "Invalid file type. Only Excel files (.xlsx, .xls) are allowed."
      );
    }

    // Save uploaded file
    const filePath = await saveUploadedFile(file, datasetsDir);

    // Get file stats
    const stats = await fs.stat(filePath);
    const fileSize = stats.size;

    // Analyze the Excel file
    const { columns, rowCount } = await analyzeExcelFile(filePath);

    // Create dataset record
    return await this.datasetRepo.create({
      projectId: projectId && !isNaN(projectId) ? projectId : null,
      name,
      description,
      filePath,
      fileName: file.name,
      fileSize,
      columns,
      rowCount,
    });
  }

  async deleteDataset(id: number) {
    const dataset = await this.datasetRepo.findById(id);

    if (!dataset) {
      throw new NotFoundError("Dataset");
    }

    // Delete the file from filesystem if it exists
    try {
      await fs.unlink(dataset.filePath);
    } catch (fileError: any) {
      // Ignore ENOENT (file not found) errors, but log others
      if (fileError.code !== "ENOENT") {
        logger.warn(
          { error: fileError, filePath: dataset.filePath },
          "Failed to delete file"
        );
      }
    }

    // Delete dataset record
    await this.datasetRepo.delete(id);
    return dataset;
  }
}
