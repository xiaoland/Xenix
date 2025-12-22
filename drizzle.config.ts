import { defineConfig } from 'drizzle-kit';

// Ensure DATABASE_URL is provided
if (!process.env.DATABASE_URL) {
  throw new Error('DATABASE_URL environment variable is required. Please set it in your .env file.');
}

// Determine database type from environment variable or DATABASE_URL
const databaseType = process.env.DATABASE_TYPE || 
  (process.env.DATABASE_URL.startsWith('sqlite') ? 'sqlite' : 'postgresql');

const dialect = databaseType === 'sqlite' ? 'sqlite' : 'postgresql';

export default defineConfig({
  schema: './server/database/schema.ts',
  out: './server/database/migrations',
  dialect,
  dbCredentials: {
    url: process.env.DATABASE_URL,
  },
});
