#!/usr/bin/env node
/**
 * Unused Export Detection Script
 *
 * Checks for:
 * 1. Exports in feature index.ts files that are not used elsewhere
 * 2. Components that are exported but never imported
 * 3. Orphaned utility functions
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const rootDir = path.resolve(__dirname, "..");

const FEATURES_DIR = path.join(rootDir, "packages/frontend/src/features");
const FRONTEND_SRC = path.join(rootDir, "packages/frontend/src");

// Colors for output
const colors: Record<string, string> = {
  reset: "\x1b[0m",
  red: "\x1b[31m",
  green: "\x1b[32m",
  yellow: "\x1b[33m",
  blue: "\x1b[34m",
};

function log(message: string, color = "reset"): void {
  console.log(`${colors[color]}${message}${colors.reset}`);
}

function error(message: string): void {
  console.error(`${colors.red}✗ ${message}${colors.reset}`);
}

function success(message: string): void {
  console.log(`${colors.green}✓ ${message}${colors.reset}`);
}

function warn(message: string): void {
  console.log(`${colors.yellow}⚠ ${message}${colors.reset}`);
}

interface ExportInfo {
  name: string;
  file: string;
  type: "component" | "function" | "type" | "unknown";
}

// Get all TypeScript/Vue files recursively
function getAllFiles(dir: string, extensions: string[]): string[] {
  const files: string[] = [];

  if (!fs.existsSync(dir)) {
    return files;
  }

  const items = fs.readdirSync(dir);

  for (const item of items) {
    const fullPath = path.join(dir, item);
    const stat = fs.statSync(fullPath);

    if (stat.isDirectory()) {
      // Skip node_modules and dist
      if (item !== "node_modules" && item !== "dist") {
        files.push(...getAllFiles(fullPath, extensions));
      }
    } else if (extensions.some((ext) => item.endsWith(ext))) {
      files.push(fullPath);
    }
  }

  return files;
}

// Extract exports from index.ts files
function extractExports(filePath: string): ExportInfo[] {
  const content = fs.readFileSync(filePath, "utf-8");
  const exports: ExportInfo[] = [];

  // Match export { name } from './path'
  const exportFromPattern =
    /export\s+\{\s*([^}]+)\s*\}\s+from\s+["']([^"']+)["']/g;
  let match: RegExpExecArray | null = exportFromPattern.exec(content);
  while (match !== null) {
    const names = match[1].split(",").map((n) => n.trim());
    for (const name of names) {
      if (name) {
        exports.push({
          name,
          file: filePath,
          type: inferType(name),
        });
      }
    }
    match = exportFromPattern.exec(content);
  }

  // Match export { name }
  const exportPattern = /export\s+\{\s*([^}]+)\s*\}/g;
  match = exportPattern.exec(content);
  while (match !== null) {
    const names = match[1].split(",").map((n) => n.trim());
    for (const name of names) {
      if (name && !name.includes("from")) {
        exports.push({
          name,
          file: filePath,
          type: inferType(name),
        });
      }
    }
    match = exportPattern.exec(content);
  }

  // Match export * from './path'
  const exportAllPattern = /export\s+\*\s+from\s+["']([^"']+)["']/g;
  match = exportAllPattern.exec(content);
  while (match !== null) {
    // For export *, we need to check the source file
    const sourcePath = match[1];
    const resolvedPath = resolveImportPath(filePath, sourcePath);
    if (resolvedPath) {
      const sourceExports = extractExports(resolvedPath);
      exports.push(...sourceExports);
    }
    match = exportAllPattern.exec(content);
  }

  // Match export default
  const exportDefaultPattern =
    /export\s+default\s+(?:class|function|const|let|var)?\s*(\w+)/;
  const defaultMatch = exportDefaultPattern.exec(content);
  if (defaultMatch) {
    exports.push({
      name: "default",
      file: filePath,
      type: inferType(defaultMatch[1]),
    });
  }

  return exports;
}

// Infer type from name
function inferType(name: string): ExportInfo["type"] {
  if (!name) return "unknown";
  if (name.endsWith("View") || name.endsWith("Component")) {
    return "component";
  }
  if (/^[A-Z]/.test(name)) {
    return "component";
  }
  if (name.startsWith("use")) {
    return "function";
  }
  return "unknown";
}

// Resolve import path to absolute path
function resolveImportPath(
  fromFile: string,
  importPath: string,
): string | null {
  const fromDir = path.dirname(fromFile);

  // Try different extensions
  const extensions = [".ts", ".tsx", ".vue", "/index.ts", "/index.vue"];

  for (const ext of extensions) {
    const fullPath = path.resolve(fromDir, importPath + ext);
    if (fs.existsSync(fullPath)) {
      return fullPath;
    }
  }

  return null;
}

// Check if an export is used in other files
function isExportUsed(
  exportName: string,
  exportFile: string,
  allFiles: string[],
): boolean {
  // Get relative path from frontend src
  const relativeExportPath = path.relative(FRONTEND_SRC, exportFile);
  const exportDir = path.dirname(relativeExportPath);

  for (const file of allFiles) {
    // Skip the export file itself
    if (file === exportFile) continue;

    const content = fs.readFileSync(file, "utf-8");

    // Check for direct import of the export
    const importPattern = new RegExp(
      `import\\s+.*?\\{[^}]*\\b${exportName}\\b[^}]*\\}\\s+from`,
      "g",
    );
    if (importPattern.test(content)) {
      return true;
    }

    // Check for default import
    if (exportName === "default") {
      const defaultImportPattern = /import\s+\w+\s+from\s+["'][^"']+["']/g;
      if (defaultImportPattern.test(content)) {
        // Check if importing from this file
        const importPathMatch = /from\s+["']([^"']+)["']/.exec(content);
        if (importPathMatch) {
          const resolved = resolveImportPath(file, importPathMatch[1]);
          if (resolved === exportFile) {
            return true;
          }
        }
      }
    }

    // Check for barrel import (import from feature folder)
    const barrelPattern = new RegExp(
      `import\\s+.*?\\{[^}]*\\b${exportName}\\b[^}]*\\}\\s+from\s+["']@/features/`,
      "g",
    );
    if (barrelPattern.test(content)) {
      return true;
    }
  }

  return false;
}

// Main check function
function checkUnusedExports(): void {
  log("🔍 Checking for unused exports...\n", "blue");

  let hasWarnings = false;
  const allExports: ExportInfo[] = [];

  // Get all feature index.ts files
  const featureDirs = fs.readdirSync(FEATURES_DIR);
  for (const feature of featureDirs) {
    const indexFile = path.join(FEATURES_DIR, feature, "index.ts");
    if (fs.existsSync(indexFile)) {
      const exports = extractExports(indexFile);
      allExports.push(...exports);
    }
  }

  // Get all source files
  const allFiles = getAllFiles(FRONTEND_SRC, [".ts", ".vue"]);

  log(`Found ${allExports.length} export(s) in feature indices\n`, "blue");

  // Check each export
  for (const exp of allExports) {
    const isUsed = isExportUsed(exp.name, exp.file, allFiles);

    if (!isUsed) {
      warn(
        `Unused export: ${exp.name} (${exp.type}) in ${path.relative(rootDir, exp.file)}`,
      );
      hasWarnings = true;
    } else {
      success(`Used: ${exp.name}`);
    }
  }

  log("");

  // Summary
  const unusedCount = allExports.filter(
    (e) => !isExportUsed(e.name, e.file, allFiles),
  ).length;

  if (hasWarnings) {
    log(`\n⚠️  Found ${unusedCount} unused export(s)`, "yellow");
    log(
      "Consider removing unused exports or mark them as intentionally exported\n",
      "yellow",
    );
    process.exit(0); // Exit 0 for warnings, can be changed to 1 for strict mode
  } else {
    log("\n✅ All exports are being used!", "green");
    process.exit(0);
  }
}

// Run the check
checkUnusedExports();
