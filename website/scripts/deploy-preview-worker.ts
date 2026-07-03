import { execFileSync } from "node:child_process";
import { appendFileSync, readFileSync } from "node:fs";
import { loadLocalDevVars, optionalEnv, requireEnv } from "./env";

loadLocalDevVars();
requireEnv("XENIX_DOWNLOAD_URL");
requireEnv("XENIX_D1_DATABASE_ID");
requireEnv("XENIX_D1_DATABASE_NAME");

function readPullRequestNumber(): number | undefined {
  const eventPath = process.env.GITHUB_EVENT_PATH;
  if (!eventPath) {
    return undefined;
  }

  const event = JSON.parse(readFileSync(eventPath, "utf8")) as {
    pull_request?: { number?: number };
    number?: number;
  };

  return event.pull_request?.number ?? event.number;
}

function slugify(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 40);
}

const pullRequestNumber = readPullRequestNumber();
const branchName = process.env.GITHUB_HEAD_REF || process.env.GITHUB_REF_NAME || "preview";
const suffix = pullRequestNumber ? `pr-${pullRequestNumber}` : slugify(branchName) || "preview";
const workerPrefix = optionalEnv("XENIX_PREVIEW_WORKER_PREFIX") ?? "xenix-website";
const workerName = `${workerPrefix}-${suffix}`;
const workersSubdomain = requireEnv("CLOUDFLARE_WORKERS_SUBDOMAIN");
const apiOrigin = `https://${workerName}.${workersSubdomain}.workers.dev`;

process.env.XENIX_WORKER_NAME = workerName;
process.env.XENIX_WORKER_ROUTE = "";

execFileSync(scriptRunnerCommand(), ["scripts/run-worker.ts", "deploy"], {
  stdio: "inherit",
  shell: process.platform === "win32",
});

if (process.env.GITHUB_ENV) {
  appendFileSync(process.env.GITHUB_ENV, `VITE_API_ORIGIN=${apiOrigin}\n`);
  appendFileSync(process.env.GITHUB_ENV, `PREVIEW_WORKER_NAME=${workerName}\n`);
}

console.log(`Preview Worker: ${workerName}`);
console.log(`VITE_API_ORIGIN=${apiOrigin}`);

function scriptRunnerCommand(): string {
  return process.platform === "win32" ? "tsx.cmd" : "tsx";
}
