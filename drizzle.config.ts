import { defineConfig } from 'drizzle-kit';

// Ensure DATABASE_URL is provided
if (!process.env.DATABASE_URL) {
  throw new Error('DATABASE_URL environment variable is required. Please set it in your .env file.');
}

// Determine database type from environment variable or DATABASE_URL
const databaseType = process.env.DATABASE_TYPE || 
  (process.env.DATABASE_URL.startsWith('sqlite') || process.env.DATABASE_URL.endsWith('.db') ? 'sqlite' : 'postgresql');

const dialect = databaseType === 'sqlite' ? 'sqlite' : 'postgresql';

// For SQLite, remove the sqlite:// prefix if present for drizzle-kit
const dbUrl = databaseType === 'sqlite' 
  ? process.env.DATABASE_URL.replace(/^sqlite:\/\//, '')
  : process.env.DATABASE_URL;

export default defineConfig({
  schema: './server/database/schema.ts',
  out: './server/database/migrations',
  dialect,
  dbCredentials: {
    url: dbUrl,
  },
});
