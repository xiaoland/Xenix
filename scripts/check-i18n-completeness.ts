#!/usr/bin/env node
/**
 * i18n Completeness Validation Script
 *
 * Validates that:
 * 1. All locale files have the same keys
 * 2. No hardcoded strings in Vue files (complement to ESLint)
 * 3. All i18n keys are used in the codebase
 * 4. No missing translations
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const rootDir = path.resolve(__dirname, "..");

const LOCALES_DIR = path.join(rootDir, "packages/frontend/public/locales");
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

// Get all locale files
function getLocaleFiles(): {
  lang: string;
  path: string;
  data: Record<string, unknown>;
}[] {
  const files: { lang: string; path: string; data: Record<string, unknown> }[] =
    [];

  if (!fs.existsSync(LOCALES_DIR)) {
    return files;
  }

  const items = fs.readdirSync(LOCALES_DIR);

  for (const item of items) {
    if (item.endsWith(".json")) {
      const lang = item.replace(".json", "");
      const filePath = path.join(LOCALES_DIR, item);
      const content = fs.readFileSync(filePath, "utf-8");
      files.push({
        lang,
        path: filePath,
        data: JSON.parse(content),
      });
    }
  }

  return files;
}

// Flatten nested object to dot notation keys
function flattenKeys(obj: Record<string, unknown>, prefix = ""): string[] {
  const keys: string[] = [];

  for (const key of Object.keys(obj)) {
    const newKey = prefix ? `${prefix}.${key}` : key;
    const value = obj[key];

    if (typeof value === "object" && value !== null && !Array.isArray(value)) {
      keys.push(...flattenKeys(value as Record<string, unknown>, newKey));
    } else {
      keys.push(newKey);
    }
  }

  return keys;
}

// Get all Vue and TS files
function getSourceFiles(): string[] {
  const files: string[] = [];

  function scanDir(dir: string): void {
    if (!fs.existsSync(dir)) return;

    const items = fs.readdirSync(dir);
    for (const item of items) {
      const fullPath = path.join(dir, item);
      const stat = fs.statSync(fullPath);

      if (stat.isDirectory()) {
        if (item !== "node_modules" && item !== "dist") {
          scanDir(fullPath);
        }
      } else if (item.endsWith(".vue") || item.endsWith(".ts")) {
        files.push(fullPath);
      }
    }
  }

  scanDir(FRONTEND_SRC);
  return files;
}

// Extract i18n keys used in code
function extractUsedKeys(filePath: string): string[] {
  const content = fs.readFileSync(filePath, "utf-8");
  const keys: string[] = [];

  // Match $t('key') or t('key')
  const tPattern = /\$?t\(['"]([^'"]+)['"]\)/g;
  let match: RegExpExecArray | null = tPattern.exec(content);
  while (match !== null) {
    keys.push(match[1]);
    match = tPattern.exec(content);
  }

  // Match $t("key") with double quotes
  const tDoublePattern = /\$?t\(["']([^"']+)["']\)/g;
  match = tDoublePattern.exec(content);
  while (match !== null) {
    if (!keys.includes(match[1])) {
      keys.push(match[1]);
    }
    match = tDoublePattern.exec(content);
  }

  return keys;
}

// Check for potential hardcoded strings in Vue templates
function checkHardcodedStrings(filePath: string): string[] {
  const content = fs.readFileSync(filePath, "utf-8");
  const issues: string[] = [];

  // Only check Vue files
  if (!filePath.endsWith(".vue")) return issues;

  // Extract template section
  const templateMatch = content.match(
    /\u003ctemplate\u003e([\s\S]*?)\u003c\/template\u003e/,
  );
  if (!templateMatch) return issues;

  const template = templateMatch[1];

  // Check for text content that might be hardcoded
  // Look for text between tags that's not whitespace or interpolation
  const textPattern = />\s*([A-Za-z][A-Za-z\s]{2,}[a-z])\s*\u003c/g;
  let match: RegExpExecArray | null = textPattern.exec(template);
  while (match !== null) {
    const text = match[1].trim();
    // Filter out common non-translatable text
    if (
      text &&
      !text.match(/^[\d\s\W]+$/) && // Not just numbers/symbols
      !text.match(/^(true|false|null|undefined)$/) && // Not keywords
      text.length > 2 // Not too short
    ) {
      issues.push(text);
    }
    match = textPattern.exec(template);
  }

  return issues;
}

// Main check function
function checkI18nCompleteness(): void {
  log("🔍 Checking i18n completeness...\n", "blue");

  let hasErrors = false;
  let hasWarnings = false;

  // Get all locale files
  const locales = getLocaleFiles();
  log(`Found ${locales.length} locale file(s)\n`, "blue");

  if (locales.length === 0) {
    error("No locale files found!");
    process.exit(1);
  }

  // Check 1: All locales should have the same keys
  log("Checking key consistency across locales...", "blue");
  const allKeys = locales.map((l) => ({
    lang: l.lang,
    keys: new Set(flattenKeys(l.data)),
  }));

  const baseKeys = allKeys[0].keys;

  for (let i = 1; i < allKeys.length; i++) {
    const { lang, keys } = allKeys[i];

    // Check for missing keys
    for (const key of baseKeys) {
      if (!keys.has(key)) {
        error(`Missing key in ${lang}: ${key}`);
        hasErrors = true;
      }
    }

    // Check for extra keys
    for (const key of keys) {
      if (!baseKeys.has(key)) {
        error(`Extra key in ${lang}: ${key}`);
        hasErrors = true;
      }
    }
  }

  if (!hasErrors) {
    success("All locales have consistent keys");
  }

  log("");

  // Check 2: Find unused i18n keys
  log("Checking for unused i18n keys...", "blue");
  const sourceFiles = getSourceFiles();
  const usedKeys = new Set<string>();

  for (const file of sourceFiles) {
    const keys = extractUsedKeys(file);
    for (const key of keys) {
      usedKeys.add(key);
    }
  }

  const unusedKeys: string[] = [];
  for (const key of baseKeys) {
    // Check if key is used (support nested keys)
    const isUsed = Array.from(usedKeys).some(
      (usedKey) => usedKey === key || key.startsWith(usedKey + "."),
    );

    if (!isUsed) {
      unusedKeys.push(key);
    }
  }

  if (unusedKeys.length > 0) {
    for (const key of unusedKeys.slice(0, 10)) {
      warn(`Potentially unused key: ${key}`);
    }
    if (unusedKeys.length > 10) {
      warn(`... and ${unusedKeys.length - 10} more`);
    }
    hasWarnings = true;
  } else {
    success("All i18n keys appear to be used");
  }

  log("");

  // Check 3: Check for hardcoded strings
  log("Checking for hardcoded strings...", "blue");
  const vueFiles = sourceFiles.filter((f) => f.endsWith(".vue"));
  let hardcodedCount = 0;

  for (const file of vueFiles) {
    const hardcoded = checkHardcodedStrings(file);
    if (hardcoded.length > 0) {
      for (const text of hardcoded.slice(0, 3)) {
        warn(
          `Potential hardcoded string in ${path.relative(rootDir, file)}: "${text}"`,
        );
        hardcodedCount++;
      }
    }
  }

  if (hardcodedCount === 0) {
    success("No obvious hardcoded strings found");
  } else {
    hasWarnings = true;
  }

  log("");

  // Summary
  if (hasErrors) {
    log("\n❌ i18n validation FAILED", "red");
    process.exit(1);
  } else if (hasWarnings) {
    log("\n⚠️  i18n validation completed with warnings", "yellow");
    process.exit(0);
  } else {
    log("\n✅ i18n validation PASSED", "green");
    log(`\nSummary:`, "blue");
    log(`  - Locales: ${locales.length}`, "blue");
    log(`  - Total keys: ${baseKeys.size}`, "blue");
    log(`  - Used keys: ${usedKeys.size}`, "blue");
    process.exit(0);
  }
}

// Run the check
checkI18nCompleteness();
