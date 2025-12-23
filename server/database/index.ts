import { drizzle } from 'drizzle-orm/better-sqlite3';
import Database from 'better-sqlite3';
import * as schema from './schema';

// Ensure DATABASE_URL is provided
if (!process.env.DATABASE_URL) {
  throw new Error('DATABASE_URL environment variable is required');
}

const connectionString = process.env.DATABASE_URL;

// Extract database path from sqlite:// or file: prefix if present
const dbPath = connectionString.replace(/^(sqlite:\/\/|file:)/, '');
const sqlite = new Database(dbPath);

// Create drizzle instance
export const db = drizzle(sqlite, { schema });

export { schema };

