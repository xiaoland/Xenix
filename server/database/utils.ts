/**
 * Cached database type to avoid repeated detection
 */
let cachedDatabaseType: 'postgresql' | 'sqlite' | null = null;

/**
 * Utility function to determine the database type from environment variables
 * @returns 'postgresql' or 'sqlite'
 */
export function getDatabaseType(): 'postgresql' | 'sqlite' {
  // Return cached value if available
  if (cachedDatabaseType) {
    return cachedDatabaseType;
  }
  
  const databaseUrl = process.env.DATABASE_URL || '';
  const databaseType = process.env.DATABASE_TYPE;
  
  // If DATABASE_TYPE is explicitly set, use it
  if (databaseType === 'postgresql' || databaseType === 'sqlite') {
    cachedDatabaseType = databaseType;
    return databaseType;
  }
  
  // Auto-detect from DATABASE_URL with more precise pattern matching
  // SQLite URLs: sqlite://, file:, or paths ending in .db/.sqlite/.sqlite3
  if (
    databaseUrl.startsWith('sqlite://') ||
    databaseUrl.startsWith('file:') ||
    /\.(db|sqlite|sqlite3)$/.test(databaseUrl)
  ) {
    cachedDatabaseType = 'sqlite';
    return 'sqlite';
  }
  
  // Default to PostgreSQL for postgresql:// or any other format
  cachedDatabaseType = 'postgresql';
  return 'postgresql';
}

