import { defineConfig } from 'drizzle-kit';

// Ensure DATABASE_URL is provided
if (!process.env.DATABASE_URL) {
  throw new Error('DATABASE_URL environment variable is required. Please set it in your .env file.');
}

const databaseUrl = process.env.DATABASE_URL;

// For SQLite, remove the sqlite:// or file: prefix if present for drizzle-kit
const dbUrl = databaseUrl.replace(/^(sqlite:\/\/|file:)/, '');

export default defineConfig({
  schema: './server/database/schema.ts',
  out: './server/database/migrations',
  dialect: 'sqlite',
  dbCredentials: {
    url: dbUrl,
  },
});

