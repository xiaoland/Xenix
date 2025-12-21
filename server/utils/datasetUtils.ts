import crypto from 'crypto';
import * as XLSX from 'xlsx';

export function generateDatasetId(): string {
  return `dataset_${Date.now()}_${crypto.randomBytes(8).toString('hex')}`;
}

export async function analyzeExcelFile(filePath: string): Promise<{
  columns: string[];
  rowCount: number;
}> {
  const workbook = XLSX.readFile(filePath);
  const firstSheetName = workbook.SheetNames[0];
  const worksheet = workbook.Sheets[firstSheetName];
  const data = XLSX.utils.sheet_to_json(worksheet);
  
  const columns = data.length > 0 ? Object.keys(data[0]) : [];
  const rowCount = data.length;
  
  return { columns, rowCount };
}
