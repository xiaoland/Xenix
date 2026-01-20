import { defineConfig } from "tsup";

export default defineConfig({
  entry: ["src/index.ts"],
  format: ["esm"],
  target: "es2022",
  outDir: "dist",
  clean: true,
  sourcemap: true,
  splitting: false,
  treeshake: false,
  minify: false,
  dts: false,
  // Bundle only @xenix/shared (source dependencies pattern)
  noExternal: ['@xenix/shared'],
});
