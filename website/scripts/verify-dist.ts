import { existsSync, readFileSync, statSync } from "node:fs";
import path from "node:path";

const requiredFiles = [
  "dist/index.html",
  "dist/images/xenix/PixPin_2026-06-11_21-36-46.png",
  "dist/images/xenix/PixPin_2026-06-11_21-37-43.png",
  "dist/images/xenix/PixPin_2026-06-11_21-38-12.png",
];

for (const file of requiredFiles) {
  const fullPath = path.resolve(file);
  if (!existsSync(fullPath) || statSync(fullPath).size === 0) {
    throw new Error(`Missing or empty build output: ${file}`);
  }
}

const html = readFileSync(path.resolve("dist/index.html"), "utf8");
if (!html.includes("Xenix") || !html.includes("/assets/")) {
  throw new Error("Built homepage does not include expected content/assets.");
}

console.log("dist verification passed");
