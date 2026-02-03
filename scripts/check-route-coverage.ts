#!/usr/bin/env node
/**
 * Route Coverage Check Script
 *
 * Validates that:
 * 1. All routes map to existing feature pages
 * 2. All feature pages are referenced by routes
 * 3. Route naming conventions are followed
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const rootDir = path.resolve(__dirname, "..");

const ROUTES_FILE = path.join(rootDir, "packages/frontend/src/routes/index.ts");
const FEATURES_DIR = path.join(rootDir, "packages/frontend/src/features");

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

interface Route {
  path: string;
  name: string | null;
  component: string;
}

interface FeaturePage {
  feature: string;
  file: string;
  fullPath: string;
  importPath: string;
}

// Extract routes from the routes file
function extractRoutes(content: string): Route[] {
  const routes: Route[] = [];

  // Match route definitions with their components
  const routePattern =
    /\{\s*path:\s*["']([^"']+)["']\s*,\s*name:\s*["']([^"']+)["']\s*,\s*component:\s*\(\)\s*=>\s*import\(["']([^"']+)["']\)/g;

  let match: RegExpExecArray | null = routePattern.exec(content);
  while (match !== null) {
    routes.push({
      path: match[1],
      name: match[2],
      component: match[3],
    });
    match = routePattern.exec(content);
  }

  // Also match child routes
  const childRoutePattern =
    /path:\s*["']([^"']+)["']\s*,\s*(?:name:\s*["']([^"']+)["']\s*,\s*)?component:\s*\(\)\s*=>\s*import\(["']([^"']+)["']\)/g;

  match = childRoutePattern.exec(content);
  while (match !== null) {
    // Avoid duplicates
    const exists = routes.some((r) => r.component === match[3]);
    if (!exists && match[3]) {
      routes.push({
        path: match[1],
        name: match[2] || null,
        component: match[3],
      });
    }
    match = childRoutePattern.exec(content);
  }

  return routes;
}

// Get all feature pages
function getFeaturePages(): FeaturePage[] {
  const pages: FeaturePage[] = [];

  if (!fs.existsSync(FEATURES_DIR)) {
    return pages;
  }

  const features = fs.readdirSync(FEATURES_DIR);

  for (const feature of features) {
    const pagesDir = path.join(FEATURES_DIR, feature, "pages");

    if (fs.existsSync(pagesDir)) {
      const files = fs.readdirSync(pagesDir);

      for (const file of files) {
        if (file.endsWith(".vue")) {
          pages.push({
            feature,
            file,
            fullPath: path.join(pagesDir, file),
            importPath: `../features/${feature}/pages/${file}`,
          });
        }
      }
    }
  }

  return pages;
}

// Validate route naming conventions
function validateRouteName(route: Route): string[] {
  const issues: string[] = [];

  if (!route.name) {
    issues.push("Missing route name");
  } else {
    // Check PascalCase naming
    if (!/^[A-Z][a-zA-Z0-9]*$/.test(route.name)) {
      issues.push(`Route name "${route.name}" should be PascalCase`);
    }
  }

  // Check component path follows convention
  if (!route.component.includes("/features/")) {
    issues.push(`Component should be in features/ directory`);
  }

  return issues;
}

// Main check function
function checkRouteCoverage(): void {
  log("🔍 Checking route coverage...\n", "blue");

  let hasErrors = false;

  // Read routes file
  if (!fs.existsSync(ROUTES_FILE)) {
    error(`Routes file not found: ${ROUTES_FILE}`);
    process.exit(1);
  }

  const routesContent = fs.readFileSync(ROUTES_FILE, "utf-8");
  const routes = extractRoutes(routesContent);

  log(`Found ${routes.length} route(s) defined\n`, "blue");

  // Get all feature pages
  const featurePages = getFeaturePages();
  log(`Found ${featurePages.length} feature page(s)\n`, "blue");

  // Check 1: All routes must have valid components
  log("Checking route component existence...", "blue");
  for (const route of routes) {
    const componentPath = path.join(
      rootDir,
      "packages/frontend/src/routes",
      route.component,
    );

    if (!fs.existsSync(componentPath)) {
      error(`Route "${route.name}" component not found: ${route.component}`);
      hasErrors = true;
    } else {
      success(`Route "${route.name}" → ${route.component}`);
    }

    // Validate naming conventions
    const namingIssues = validateRouteName(route);
    for (const issue of namingIssues) {
      warn(`Route "${route.name ?? "unknown"}": ${issue}`);
    }
  }

  log("");

  // Check 2: All feature pages should be referenced by routes
  log("Checking feature page coverage...", "blue");
  const usedComponents = new Set(routes.map((r) => r.component));

  for (const page of featurePages) {
    const isUsed = usedComponents.has(page.importPath);

    if (!isUsed) {
      warn(`Feature page not used by any route: ${page.importPath}`);
    } else {
      success(`Feature page referenced: ${page.importPath}`);
    }
  }

  log("");

  // Summary
  if (hasErrors) {
    log("\n❌ Route coverage check FAILED", "red");
    process.exit(1);
  } else {
    log("\n✅ Route coverage check PASSED", "green");
    log(`\nSummary:`, "blue");
    log(`  - Routes defined: ${routes.length}`, "blue");
    log(`  - Feature pages: ${featurePages.length}`, "blue");
    log(`  - Coverage: ${routes.length}/${featurePages.length} pages`, "blue");
    process.exit(0);
  }
}

// Run the check
checkRouteCoverage();
