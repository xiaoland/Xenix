import { defineConfig } from "tsup";

export default defineConfig({
  entry: ["src/index.ts"],
  format: ["esm"],
  target: "es2022",
  outDir: "dist-fc",
  clean: true,
  sourcemap: false, // Disable for production
  splitting: false,
  treeshake: true,
  minify: false, // Keep readable for debugging
  dts: false,

  // Bundle ALL dependencies (critical for FC)
  noExternal: [/.*/],

  // These are Node.js built-ins, should not be bundled
  external: [
    "child_process",
    "crypto",
    "fs",
    "path",
    "os",
    "stream",
    "http",
    "https",
    "net",
    "tls",
    "zlib",
    "url",
    "util",
    "events",
    "buffer",
    "querystring",
  ],

  // Shim Node.js built-ins for proper ESM handling
  shims: true,

  // Inject __dirname and __filename for Python path resolution
  banner: {
    js: `import { fileURLToPath } from 'url';
import { dirname } from 'path';
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);`,
  },
});
