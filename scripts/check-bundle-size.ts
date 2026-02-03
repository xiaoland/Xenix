#!/usr/bin/env node
/**
 * Bundle Size Check Script
 *
 * Validates that production build chunks stay within budget
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";
import { exec } from "node:child_process";

const execAsync = promisify(exec);

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const rootDir = path.resolve(__dirname, "..");

const DIST_DIR = path.join(rootDir, "packages/frontend/dist");
const BUDGET_FILE = path.join(rootDir, "packages/frontend/bundle-budget.json");

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

// Parse size string (e.g., "500 KB") to bytes
function parseSize(sizeStr: string): number {
  const match = sizeStr.match(/^(\d+(?:\.\d+)?)\s*(B|KB|MB|GB)$/i);
  if (!match) return 0;

  const size = parseFloat(match[1]);
  const unit = match[2].toUpperCase();

  const multipliers: Record<string, number> = {
    B: 1,
    KB: 1024,
    MB: 1024 * 1024,
    GB: 1024 * 1024 * 1024,
  };

  return size * (multipliers[unit] || 1);
}

// Format bytes to human readable
function formatSize(bytes: number): string {
  if (bytes === 0) return "0 B";

  const units = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));

  return `${(bytes / Math.pow(1024, i)).toFixed(2)} ${units[i]}`;
}

// Get file size
function getFileSize(filePath: string): number {
  try {
    const stats = fs.statSync(filePath);
    return stats.size;
  } catch {
    return 0;
  }
}

// Get gzipped size
async function getGzippedSize(filePath: string): Promise<number> {
  try {
    const { stdout } = await execAsync(`gzip -c "${filePath}" | wc -c`, {
      encoding: "utf-8",
    });
    return parseInt(stdout.trim(), 10);
  } catch {
    return 0;
  }
}

interface BudgetConfig {
  budgets: Record<
    string,
    {
      limit: string;
      description: string;
    }
  >;
  total: {
    limit: string;
    description: string;
  };
  gzip: boolean;
  brotli: boolean;
}

// Main check function
async function checkBundleSize(): Promise<void> {
  log("📦 Checking bundle size budgets...\n", "blue");

  // Check if dist exists
  if (!fs.existsSync(DIST_DIR)) {
    error(`Build output not found: ${DIST_DIR}`);
    log("\nPlease run 'pnpm run build:frontend' first", "yellow");
    process.exit(1);
  }

  // Load budget config
  if (!fs.existsSync(BUDGET_FILE)) {
    error(`Budget config not found: ${BUDGET_FILE}`);
    process.exit(1);
  }

  const budgetConfig: BudgetConfig = JSON.parse(
    fs.readFileSync(BUDGET_FILE, "utf-8"),
  );

  // Get all JS files in dist
  const jsFiles: string[] = [];
  function scanDir(dir: string): void {
    const items = fs.readdirSync(dir);
    for (const item of items) {
      const fullPath = path.join(dir, item);
      const stat = fs.statSync(fullPath);
      if (stat.isDirectory()) {
        scanDir(fullPath);
      } else if (item.endsWith(".js")) {
        jsFiles.push(fullPath);
      }
    }
  }
  scanDir(DIST_DIR);

  log(`Found ${jsFiles.length} JS file(s) in dist\n`, "blue");

  let hasErrors = false;
  let hasWarnings = false;
  let totalSize = 0;
  let totalGzipped = 0;

  // Check each file against budgets
  log("Checking individual chunk budgets...", "blue");

  for (const file of jsFiles) {
    const fileName = path.basename(file);
    const size = getFileSize(file);
    const gzipped = await getGzippedSize(file);

    totalSize += size;
    totalGzipped += gzipped;

    // Find matching budget
    let budgetName = "lazy-chunks";
    for (const name of Object.keys(budgetConfig.budgets)) {
      if (fileName.includes(name)) {
        budgetName = name;
        break;
      }
    }

    const budget = budgetConfig.budgets[budgetName];
    if (budget) {
      const budgetBytes = parseSize(budget.limit);

      if (size > budgetBytes) {
        error(
          `${fileName}: ${formatSize(size)} exceeds budget ${budget.limit} (${budget.description})`,
        );
        hasErrors = true;
      } else if (size > budgetBytes * 0.9) {
        warn(
          `${fileName}: ${formatSize(size)} is at 90% of budget ${budget.limit}`,
        );
        hasWarnings = true;
      } else {
        success(`${fileName}: ${formatSize(size)} / ${budget.limit}`);
      }
    }
  }

  log("");

  // Check total budget
  log("Checking total bundle size...", "blue");
  const totalBudget = parseSize(budgetConfig.total.limit);

  if (totalSize > totalBudget) {
    error(
      `Total size: ${formatSize(totalSize)} exceeds budget ${budgetConfig.total.limit}`,
    );
    hasErrors = true;
  } else if (totalSize > totalBudget * 0.9) {
    warn(
      `Total size: ${formatSize(totalSize)} is at 90% of budget ${budgetConfig.total.limit}`,
    );
    hasWarnings = true;
  } else {
    success(
      `Total size: ${formatSize(totalSize)} / ${budgetConfig.total.limit}`,
    );
  }

  // Report gzipped size
  if (budgetConfig.gzip) {
    log(`  Gzipped: ${formatSize(totalGzipped)}`, "blue");
  }

  log("");

  // Summary
  if (hasErrors) {
    log("\n❌ Bundle size check FAILED", "red");
    log("Some chunks exceed their budget limits", "red");
    process.exit(1);
  } else if (hasWarnings) {
    log("\n⚠️  Bundle size check completed with warnings", "yellow");
    log("Some chunks are approaching their budget limits", "yellow");
    process.exit(0);
  } else {
    log("\n✅ Bundle size check PASSED", "green");
    log(`\nSummary:`, "blue");
    log(`  - Total files: ${jsFiles.length}`, "blue");
    log(`  - Total size: ${formatSize(totalSize)}`, "blue");
    log(`  - Gzipped: ${formatSize(totalGzipped)}`, "blue");
    log(`  - Budget: ${budgetConfig.total.limit}`, "blue");
    process.exit(0);
  }
}

// Run the check
checkBundleSize().catch((err) => {
  error(`Unexpected error: ${err.message}`);
  process.exit(1);
});
