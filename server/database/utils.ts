/**
 * Utility function to determine the database type from environment variables
 * @returns 'postgresql' or 'sqlite'
 */
export function getDatabaseType(): 'postgresql' | 'sqlite' {
  const databaseUrl = process.env.DATABASE_URL || '';
  const databaseType = process.env.DATABASE_TYPE;
  
  // If DATABASE_TYPE is explicitly set, use it
  if (databaseType === 'postgresql' || databaseType === 'sqlite') {
    return databaseType;
  }
  
  // Auto-detect from DATABASE_URL
  if (databaseUrl.startsWith('sqlite') || databaseUrl.endsWith('.db')) {
    return 'sqlite';
  }
  
  // Default to PostgreSQL
  return 'postgresql';
}
