import { execFileSync } from "node:child_process";
import { writeFileSync } from "node:fs";
import { loadLocalDevVars, optionalEnv, requireEnv } from "./env";

type Command = "dev" | "dry-run" | "deploy";

const command = process.argv[2] as Command | undefined;
if (!command || !["dev", "dry-run", "deploy"].includes(command)) {
  throw new Error("Usage: tsx scripts/run-worker.ts <dev|dry-run|deploy>");
}

loadLocalDevVars();

const downloadUrl = requireEnv("XENIX_DOWNLOAD_URL");
const workerName = optionalEnv("XENIX_WORKER_NAME") ?? "xenix-website-api";
const workerRoute = optionalEnv("XENIX_WORKER_ROUTE");
const workerZoneName = optionalEnv("XENIX_WORKER_ZONE_NAME");
const d1DatabaseName = optionalEnv("XENIX_D1_DATABASE_NAME") ?? "xenix-website";
const d1DatabaseId =
  optionalEnv("XENIX_D1_DATABASE_ID") ?? "00000000-0000-0000-0000-000000000000";

if (command === "deploy") {
  requireEnv("XENIX_D1_DATABASE_ID");
  requireEnv("XENIX_D1_DATABASE_NAME");
}

const generatedConfigPath = `.wrangler-worker-${command}.toml`;
const routeBlock = workerRoute
  ? `\nroutes = [\n  { pattern = "${escapeToml(workerRoute)}"${workerZoneName ? `, zone_name = "${escapeToml(workerZoneName)}"` : ""} }\n]\n`
  : "\nworkers_dev = true\n";

writeFileSync(
  generatedConfigPath,
  `name = "${escapeToml(workerName)}"
main = "src/worker/index.ts"
compatibility_date = "2026-03-01"${routeBlock}
[[d1_databases]]
binding = "DB"
database_name = "${escapeToml(d1DatabaseName)}"
database_id = "${escapeToml(d1DatabaseId)}"
migrations_dir = "drizzle"
`,
);

const wranglerArgs =
  command === "dev"
    ? [
        "exec",
        "wrangler",
        "dev",
        "--config",
        generatedConfigPath,
        "--var",
        `XENIX_DOWNLOAD_URL:${downloadUrl}`,
        "--port",
        optionalEnv("WORKER_PORT") ?? "8787",
      ]
    : [
        "exec",
        "wrangler",
        "deploy",
        "--config",
        generatedConfigPath,
        "--var",
        `XENIX_DOWNLOAD_URL:${downloadUrl}`,
        ...(command === "dry-run" ? ["--dry-run", "--outdir", ".worker-build"] : []),
      ];

execFileSync(packageManagerCommand(), wranglerArgs, {
  stdio: "inherit",
  shell: process.platform === "win32",
});

function escapeToml(value: string): string {
  return value.replaceAll("\\", "\\\\").replaceAll('"', '\\"');
}

function packageManagerCommand(): string {
  return process.platform === "win32" ? "pnpm.cmd" : "pnpm";
}
