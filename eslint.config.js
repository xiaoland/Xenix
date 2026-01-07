import js from "@eslint/js";
import tsParser from "@typescript-eslint/parser";
import vueI18nPlugin from "@intlify/eslint-plugin-vue-i18n";
import vuePlugin from "eslint-plugin-vue";
import path from "node:path";
import { fileURLToPath } from "node:url";

import vueParser from "vue-eslint-parser";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default [
  // Ignore patterns
  {
    ignores: [
      "**/node_modules/**",
      "**/dist/**",
      "**/.output/**",
      "**/.nuxt/**",
      "**/.nitro/**",
      "**/.cache/**",
      "**/coverage/**",
      "datasets/**",
      "uploads/**",
      "data/**",
      "**/drizzle/**",
    ],
  },

  // Base JavaScript/TypeScript config
  js.configs.recommended,
  {
    files: ["**/*.ts", "**/*.js", "**/*.mjs"],
    languageOptions: {
      parser: tsParser,
      parserOptions: {
        ecmaVersion: "latest",
        sourceType: "module",
      },
      globals: {
        console: "readonly",
        process: "readonly",
        Buffer: "readonly",
        __dirname: "readonly",
        __filename: "readonly",
        module: "readonly",
        require: "readonly",
        setImmediate: "readonly",
        clearInterval: "readonly",
        setInterval: "readonly",
        setTimeout: "readonly",
        clearTimeout: "readonly",
        global: "readonly",
        URL: "readonly",
        File: "readonly",
      },
    },
    rules: {
      "no-console": "off", // Allow console for error logging
      "no-debugger": "warn",
      "no-unreachable": "error",
      "prefer-const": "warn",
      "no-unused-vars": ["warn", { argsIgnorePattern: "^_" }],
    },
  },

  // Frontend-specific globals
  {
    files: ["packages/frontend/**/*.ts", "packages/frontend/**/*.vue"],
    languageOptions: {
      globals: {
        window: "readonly",
        document: "readonly",
        navigator: "readonly",
        localStorage: "readonly",
        sessionStorage: "readonly",
        fetch: "readonly",
        FormData: "readonly",
        File: "readonly",
        Blob: "readonly",
        RequestInit: "readonly",
      },
    },
  },

  // Vue config
  ...vuePlugin.configs["flat/recommended"],
  {
    files: ["**/*.vue"],
    languageOptions: {
      parser: vueParser,
      parserOptions: {
        parser: tsParser,
        ecmaVersion: "latest",
        sourceType: "module",
      },
      globals: {
        console: "readonly",
        clearInterval: "readonly",
        setInterval: "readonly",
      },
    },
    rules: {
      "vue/multi-word-component-names": "off",
      "vue/require-default-prop": "off",
      "vue/max-attributes-per-line": "off",
      "vue/singleline-html-element-content-newline": "off",
      "vue/html-self-closing": "off",
      "vue/attributes-order": "warn",
      "vue/html-indent": "off",
      "no-unused-vars": ["warn", { argsIgnorePattern: "^_" }],
    },
  },

  // Vue i18n config for frontend
  ...vueI18nPlugin.configs["flat/recommended"],
  {
    files: ["packages/frontend/**/*.vue", "packages/frontend/**/*.ts"],
    rules: {
      "@intlify/vue-i18n/no-raw-text": "off", // Can be enabled later for stricter enforcement
      "@intlify/vue-i18n/no-unused-keys": "warn",
      "@intlify/vue-i18n/no-missing-keys": "warn",
    },
    settings: {
      "vue-i18n": {
        localeDir: path.resolve(
          __dirname,
          "./packages/frontend/public/locales/*.json"
        ),
        messageSyntaxVersion: "^11.0.0",
      },
    },
  },
];
