import { defineConfig } from "electron-vite";

export default defineConfig({
  main: {
    build: {
      externalizeDeps: true,
      lib: {
        entry: "electron/main.ts",
      },
    },
  },
  preload: {
    build: {
      externalizeDeps: true,
      lib: {
        entry: "electron/preload.ts",
      },
    },
  },
});
