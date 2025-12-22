import { defineConfig } from 'drizzle-kit';
import { getDatabaseType } from './server/database/utils';

// Ensure DATABASE_URL is provided
if (!process.env.DATABASE_URL) {
  throw new Error('DATABASE_URL environment variable is required. Please set it in your .env file.');
}

const databaseUrl = process.env.DATABASE_URL;

// Determine database type
const databaseType = getDatabaseType();
const dialect = databaseType === 'sqlite' ? 'sqlite' : 'postgresql';

// For SQLite, remove the sqlite:// or file: prefix if present for drizzle-kit
const dbUrl = databaseType === 'sqlite' 
  ? databaseUrl.replace(/^(sqlite:\/\/|file:)/, '')
  : databaseUrl;

export default defineConfig({
  schema: './server/database/schema.ts',
  out: './server/database/migrations',
  dialect,
  dbCredentials: {
    url: dbUrl,
  },
});
