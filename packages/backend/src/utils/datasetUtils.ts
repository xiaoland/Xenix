import crypto from "crypto";
import fs from "fs/promises";
import path from "path";
import * as XLSX from "xlsx";

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

export async function analyzeFileFromBuffer(
  buffer: ArrayBuffer,
  filename: string,
): Promise<{
  columns: string[];
  rowCount: number;
  duplicateCount: number;
  duplicateRows?: number[];
}> {
  const workbook = XLSX.read(buffer, { type: "buffer" });

  if (!workbook.SheetNames || workbook.SheetNames.length === 0) {
    throw new Error("File contains no sheets");
  }

  const firstSheetName = workbook.SheetNames[0];
  const worksheet = workbook.Sheets[firstSheetName];

  if (!worksheet) {
    throw new Error("Unable to read worksheet");
  }

  const data = XLSX.utils.sheet_to_json(worksheet);

  if (data.length === 0) {
    throw new Error("File contains no data rows (only header or empty)");
  }

  const firstRow = data[0];
  if (!firstRow || typeof firstRow !== "object") {
    throw new Error("Invalid file format");
  }

  const columns = Object.keys(firstRow);
  if (columns.length === 0) {
    throw new Error("File has no columns");
  }

  // Detect duplicate rows
  const seen = new Map<string, number[]>();
  const duplicateRows: number[] = [];

  data.forEach((row: any, index: number) => {
    // Create a unique key for each row by stringifying all values
    const rowKey = columns.map((col) => String(row[col] ?? "")).join("|");

    if (seen.has(rowKey)) {
      // This is a duplicate - mark the current row index
      duplicateRows.push(index + 1); // +1 because row numbers are 1-based for display
      // Also mark the first occurrence if not already marked
      const firstOccurrences = seen.get(rowKey)!;
      if (firstOccurrences.length === 1) {
        duplicateRows.push(firstOccurrences[0] + 1);
      }
      firstOccurrences.push(index);
    } else {
      seen.set(rowKey, [index]);
    }
  });

  const uniqueDuplicateRows = [...new Set(duplicateRows)].sort((a, b) => a - b);
  const duplicateCount = uniqueDuplicateRows.length;
  const rowCount = data.length; // Number of data rows (excluding header)

  return {
    columns,
    rowCount,
    duplicateCount,
    duplicateRows: duplicateCount > 0 ? uniqueDuplicateRows : undefined,
  };
}

/**
 * Remove duplicate rows from file buffer and return cleaned buffer
 */
export async function removeDuplicateRowsFromBuffer(
  buffer: ArrayBuffer,
  filename: string,
): Promise<{
  buffer: Buffer;
  originalRowCount: number;
  removedCount: number;
  newRowCount: number;
}> {
  const workbook = XLSX.read(buffer, { type: "buffer" });

  if (!workbook.SheetNames || workbook.SheetNames.length === 0) {
    throw new Error("File contains no sheets");
  }

  const firstSheetName = workbook.SheetNames[0];
  const worksheet = workbook.Sheets[firstSheetName];

  if (!worksheet) {
    throw new Error("Unable to read worksheet");
  }

  const data = XLSX.utils.sheet_to_json(worksheet);
  const originalRowCount = data.length;

  if (data.length === 0) {
    throw new Error("File contains no data rows");
  }

  const firstRow = data[0];
  if (!firstRow || typeof firstRow !== "object") {
    throw new Error("Invalid file format");
  }
  const columns = Object.keys(firstRow as object);

  // Remove duplicates while keeping first occurrence
  const seen = new Set<string>();
  const uniqueData: any[] = [];

  data.forEach((row: any) => {
    const rowKey = columns.map((col) => String(row[col] ?? "")).join("|");

    if (!seen.has(rowKey)) {
      seen.add(rowKey);
      uniqueData.push(row);
    }
  });

  // Create new worksheet with unique data
  const newWorksheet = XLSX.utils.json_to_sheet(uniqueData);
  const newWorkbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(newWorkbook, newWorksheet, firstSheetName);

  // Generate buffer
  const newBuffer = XLSX.write(newWorkbook, {
    type: "buffer",
    bookType: "xlsx",
  });

  return {
    buffer: Buffer.from(newBuffer),
    originalRowCount,
    removedCount: originalRowCount - uniqueData.length,
    newRowCount: uniqueData.length,
  };
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

/**
 * Safely parse JSON string array, returning default value on error
 */
export function safeParseJsonArray(
  value: any,
  defaultValue: any[] = [],
): any[] {
  if (Array.isArray(value)) {
    return value;
  }
  if (typeof value === "string") {
    try {
      const parsed = JSON.parse(value);
      return Array.isArray(parsed) ? parsed : defaultValue;
    } catch {
      return defaultValue;
    }
  }
  return defaultValue;
}
