import crypto from "crypto";
import * as XLSX from "xlsx";
import path from "path";
import fs from "fs/promises";

export function generateDatasetId(): string {
  return `dataset_${Date.now()}_${crypto.randomBytes(8).toString("hex")}`;
}

export async function analyzeExcelFile(filePath: string): Promise<{
  columns: string[];
  rowCount: number;
}> {
  // Read file as buffer to avoid Windows path issues with ESM loader
  const normalizedPath = path.resolve(filePath);
  const buffer = await fs.readFile(normalizedPath);
  const workbook = XLSX.read(buffer, { type: "buffer" });

  if (!workbook.SheetNames || workbook.SheetNames.length === 0) {
    throw new Error("Excel file contains no sheets");
  }

  const firstSheetName = workbook.SheetNames[0];
  const worksheet = workbook.Sheets[firstSheetName];

  if (!worksheet) {
    throw new Error("Unable to read worksheet");
  }

  const data = XLSX.utils.sheet_to_json(worksheet);

  if (data.length === 0) {
    throw new Error("Excel file contains no data rows (only header or empty)");
  }

  const firstRow = data[0];
  if (!firstRow || typeof firstRow !== "object") {
    throw new Error("Invalid Excel file format");
  }

  const columns = Object.keys(firstRow);
  if (columns.length === 0) {
    throw new Error("Excel file has no columns");
  }

  const rowCount = data.length; // Number of data rows (excluding header)

  return { columns, rowCount };
}

export function parseDatasetColumns(columns: any): string[] {
  if (typeof columns === "string") {
    try {
      return JSON.parse(columns);
    } catch {
      return [];
    }
  }
  return Array.isArray(columns) ? columns : [];
}
