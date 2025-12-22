import * as schema from './schema';
import { getDatabaseType } from './utils';

// Ensure DATABASE_URL is provided
if (!process.env.DATABASE_URL) {
  throw new Error('DATABASE_URL environment variable is required');
}

const connectionString = process.env.DATABASE_URL;
const databaseType = getDatabaseType();

let db: any;

if (databaseType === 'sqlite') {
  // Use SQLite
  const { drizzle } = await import('drizzle-orm/better-sqlite3');
  const Database = (await import('better-sqlite3')).default;
  
  // Extract database path from sqlite:// or file: prefix
  const dbPath = connectionString.replace(/^(sqlite:\/\/|file:)/, '');
  const sqlite = new Database(dbPath);
  
  db = drizzle(sqlite, { schema });
} else {
  // Use PostgreSQL
  const { drizzle } = await import('drizzle-orm/postgres-js');
  const postgres = (await import('postgres')).default;
  
  const client = postgres(connectionString);
  db = drizzle(client, { schema });
}

export { db, schema };
