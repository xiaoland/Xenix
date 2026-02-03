/**
 * Dataset utility functions for extracting metadata from files
 */
import * as XLSX from "xlsx";

export interface DatasetMetadata {
  columns: string[];
  rowCount: number;
  fileSize: number;
  duplicateCount?: number;
  duplicateRows?: number[];
}

/**
 * Detect duplicate rows in dataset data
 */
function detectDuplicates(
  data: any[],
  columns: string[],
): { duplicateCount: number; duplicateRows: number[] } {
  const seen = new Map<string, number[]>();
  const duplicateRows: number[] = [];

  data.forEach((row: any, index: number) => {
    const rowKey = columns.map((col) => String(row[col] ?? "")).join("|");

    if (seen.has(rowKey)) {
      duplicateRows.push(index + 1); // +1 for 1-based row numbers
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
  return {
    duplicateCount: uniqueDuplicateRows.length,
    duplicateRows: uniqueDuplicateRows,
  };
}

/**
 * Extract metadata from Excel or CSV file
 */
export async function extractDatasetMetadata(
  file: File,
): Promise<DatasetMetadata> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();

    reader.onload = (e) => {
      try {
        const data = e.target?.result;
        if (!data) {
          reject(new Error("Failed to read file"));
          return;
        }

        // Parse the file using xlsx
        const workbook = XLSX.read(data, { type: "binary" });

        // Get first sheet
        const firstSheetName = workbook.SheetNames[0];
        const worksheet = workbook.Sheets[firstSheetName];

        // Convert to JSON to get data
        const jsonData = XLSX.utils.sheet_to_json(worksheet, { header: 1 });

        if (jsonData.length === 0) {
          reject(new Error("File is empty"));
          return;
        }

        // First row contains column names
        const columns = (jsonData[0] as any[]).map((col) => String(col));

        // Row count (excluding header)
        const rowCount = jsonData.length - 1;

        // Detect duplicates using the data rows
        const dataRows = XLSX.utils.sheet_to_json(worksheet);
        const { duplicateCount, duplicateRows } = detectDuplicates(
          dataRows,
          columns,
        );

        resolve({
          columns,
          rowCount,
          fileSize: file.size,
          duplicateCount,
          duplicateRows,
        });
      } catch (error) {
        reject(new Error(`Failed to parse file: ${error}`));
      }
    };

    reader.onerror = () => {
      reject(new Error("Failed to read file"));
    };

    reader.readAsBinaryString(file);
  });
}
