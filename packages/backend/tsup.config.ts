import { defineConfig } from "tsup";

export default defineConfig({
  entry: ["src/index.ts"],
  format: ["cjs"],
  target: "node22",
  platform: "node",
  outDir: "dist",
  outExtension: () => ({ js: ".cjs" }),
  clean: true,
  sourcemap: true,
  splitting: false,
  treeshake: false,
  minify: false,
  dts: false,
  // Bundle only @xenix/shared (source dependencies pattern)
  noExternal: ["@xenix/shared"],
});
