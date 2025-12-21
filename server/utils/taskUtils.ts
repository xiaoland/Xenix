import crypto from 'crypto';

export function generateTaskId(): string {
  return `task_${Date.now()}_${crypto.randomBytes(8).toString('hex')}`;
}

export function validateExcelFile(filename: string): boolean {
  const validExtensions = ['.xlsx', '.xls'];
  return validExtensions.some(ext => filename.toLowerCase().endsWith(ext));
}

export async function saveUploadedFile(file: File, uploadDir: string): Promise<string> {
  const fs = await import('fs/promises');
  const path = await import('path');
  
  // Ensure upload directory exists
  await fs.mkdir(uploadDir, { recursive: true });
  
  // Generate unique filename
  const timestamp = Date.now();
  const ext = path.extname(file.name);
  const basename = path.basename(file.name, ext);
  const filename = `${basename}_${timestamp}${ext}`;
  const filepath = path.join(uploadDir, filename);
  
  // Save file
  const buffer = Buffer.from(await file.arrayBuffer());
  await fs.writeFile(filepath, buffer);
  
  return filepath;
}
