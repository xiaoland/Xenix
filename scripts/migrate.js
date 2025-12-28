#!/usr/bin/env node

import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import Database from 'better-sqlite3';
import { readFileSync, readdirSync } from 'fs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Get database URL from environment or use default
const DATABASE_URL = process.env.DATABASE_URL || './xenix.db';

// Extract database path
const dbPath = DATABASE_URL.replace(/^(sqlite:\/\/|file:)/, '');
console.log(`Using database: ${dbPath}`);

// Create database connection
const db = new Database(dbPath);

// Enable foreign keys
db.pragma('foreign_keys = ON');

// Create migrations tracking table if it doesn't exist
db.exec(`
  CREATE TABLE IF NOT EXISTS __drizzle_migrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hash TEXT NOT NULL UNIQUE,
    created_at INTEGER DEFAULT (unixepoch())
  );
`);

// Get list of applied migrations
const appliedMigrations = db.prepare('SELECT hash FROM __drizzle_migrations').all().map(r => r.hash);

// Read migration files
const migrationsDir = join(__dirname, '../server/database/migrations');
const migrationFiles = readdirSync(migrationsDir)
  .filter(f => f.endsWith('.sql'))
  .sort();

console.log(`Found ${migrationFiles.length} migration files`);
console.log(`Already applied: ${appliedMigrations.length} migrations`);

let appliedCount = 0;

// Apply each migration
for (const file of migrationFiles) {
  const hash = file;
  
  if (appliedMigrations.includes(hash)) {
    console.log(`⏭️  Skipping ${file} (already applied)`);
    continue;
  }

  const migrationPath = join(migrationsDir, file);
  const sql = readFileSync(migrationPath, 'utf8');
  
  console.log(`\n🚀 Applying migration: ${file}`);
  
  try {
    // Split by statement-breakpoint and execute each statement
    const statements = sql
      .split('--> statement-breakpoint')
      .map(s => s.trim())
      .filter(s => s.length > 0);
    
    db.exec('BEGIN TRANSACTION;');
    
    for (const statement of statements) {
      if (statement) {
        console.log(`   Executing: ${statement.substring(0, 80)}...`);
        db.exec(statement);
      }
    }
    
    // Record migration as applied
    db.prepare('INSERT INTO __drizzle_migrations (hash) VALUES (?)').run(hash);
    
    db.exec('COMMIT;');
    
    console.log(`✅ Successfully applied ${file}`);
    appliedCount++;
  } catch (error) {
    db.exec('ROLLBACK;');
    console.error(`❌ Error applying ${file}:`, error.message);
    process.exit(1);
  }
}

db.close();

console.log(`\n✨ Migration complete! Applied ${appliedCount} new migration(s)`);
