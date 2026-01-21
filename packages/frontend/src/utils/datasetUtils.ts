/**
 * Dataset utility functions for extracting metadata from files
 */
import * as XLSX from 'xlsx';

export interface DatasetMetadata {
  columns: string[];
  rowCount: number;
  fileSize: number;
}

/**
 * Extract metadata from Excel or CSV file
 */
export async function extractDatasetMetadata(file: File): Promise<DatasetMetadata> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();

    reader.onload = (e) => {
      try {
        const data = e.target?.result;
        if (!data) {
          reject(new Error('Failed to read file'));
          return;
        }

        // Parse the file using xlsx
        const workbook = XLSX.read(data, { type: 'binary' });

        // Get first sheet
        const firstSheetName = workbook.SheetNames[0];
        const worksheet = workbook.Sheets[firstSheetName];

        // Convert to JSON to get data
        const jsonData = XLSX.utils.sheet_to_json(worksheet, { header: 1 });

        if (jsonData.length === 0) {
          reject(new Error('File is empty'));
          return;
        }

        // First row contains column names
        const columns = (jsonData[0] as any[]).map(col => String(col));

        // Row count (excluding header)
        const rowCount = jsonData.length - 1;

        resolve({
          columns,
          rowCount,
          fileSize: file.size,
        });
      } catch (error) {
        reject(new Error(`Failed to parse file: ${error}`));
      }
    };

    reader.onerror = () => {
      reject(new Error('Failed to read file'));
    };

    reader.readAsBinaryString(file);
  });
}
