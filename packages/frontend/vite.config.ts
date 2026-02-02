import vue from "@vitejs/plugin-vue";
import { resolve } from "path";
import UnoCSS from "unocss/vite";
import { defineConfig } from "vite";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue(), UnoCSS()],
  resolve: {
    alias: {
      "@": resolve(__dirname, "./src"),
    },
  },
  server: {
    port: Number(process.env.FRONTEND_PORT) || 5173,
  },
  build: {
    sourcemap: true,
    // Bundle size budgets
    chunkSizeWarningLimit: 500, // Warn if chunk > 500KB
    rollupOptions: {
      output: {
        // Manual chunk splitting for better caching
        manualChunks: {
          // Vendor chunks
          "vendor-vue": ["vue", "vue-router", "pinia"],
          "vendor-ui": ["ant-design-vue"],
          "vendor-query": ["@tanstack/vue-query", "@vueuse/core"],
          "vendor-ml": ["xlsx"],
        },
        // Ensure chunks don't exceed budget
        experimentalMinChunkSize: 10000, // 10KB minimum chunk size
      },
    },
    // Report bundle size
    reportCompressedSize: true,
  },
});
