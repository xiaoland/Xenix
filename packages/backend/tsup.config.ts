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
  // Don't bundle any dependencies
  noExternal: [],
});
