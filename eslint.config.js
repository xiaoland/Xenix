import js from "@eslint/js";
import tsPlugin from "@typescript-eslint/eslint-plugin";
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
      "scripts/**",
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
        project: "./tsconfig.json",
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
    plugins: {
      "@typescript-eslint": tsPlugin,
    },
    rules: {
      "no-console": process.env.NODE_ENV === "production" ? "warn" : "off",
      "no-debugger": "error",
      "no-unreachable": "error",
      "prefer-const": "error",
      "no-unused-vars": "off",
      "@typescript-eslint/no-unused-vars": [
        "error",
        {
          argsIgnorePattern: "^_",
          varsIgnorePattern: "^_",
          caughtErrorsIgnorePattern: "^_",
        },
      ],
      "@typescript-eslint/explicit-function-return-type": "off",
      "@typescript-eslint/no-explicit-any": "warn",
      "@typescript-eslint/no-floating-promises": "error",
      "@typescript-eslint/await-thenable": "error",
      "@typescript-eslint/no-misused-promises": "error",
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
        project: "./tsconfig.json",
      },
      globals: {
        console: "readonly",
        clearInterval: "readonly",
        setInterval: "readonly",
      },
    },
    plugins: {
      "@typescript-eslint": tsPlugin,
    },
    rules: {
      "vue/multi-word-component-names": "off",
      "vue/require-default-prop": "off",
      "vue/max-attributes-per-line": "off",
      "vue/singleline-html-element-content-newline": "off",
      "vue/html-self-closing": "off",
      "vue/attributes-order": "error",
      "vue/html-indent": "off",
      "vue/no-unused-vars": "error",
      "vue/no-unused-components": "error",
      "no-unused-vars": "off",
      "@typescript-eslint/no-unused-vars": [
        "error",
        {
          argsIgnorePattern: "^_",
          varsIgnorePattern: "^_",
          caughtErrorsIgnorePattern: "^_",
        },
      ],
    },
  },

  // Vue i18n config for frontend
  ...vueI18nPlugin.configs["flat/recommended"],
  {
    files: ["packages/frontend/**/*.vue", "packages/frontend/**/*.ts"],
    rules: {
      "@intlify/vue-i18n/no-raw-text": [
        "error",
        {
          ignorePattern: "^[-#:()&]+$",
          ignoreNodes: ["md-icon", "v-icon"],
        },
      ],
      "@intlify/vue-i18n/no-unused-keys": "error",
      "@intlify/vue-i18n/no-missing-keys": "error",
      "@intlify/vue-i18n/no-dynamic-keys": "warn",
    },
    settings: {
      "vue-i18n": {
        localeDir: path.resolve(
          __dirname,
          "./packages/frontend/public/locales/*.json",
        ),
        messageSyntaxVersion: "^11.0.0",
      },
    },
  },

  // ============================================
  // Architecture Boundary Rules (Phase 3)
  // ============================================

  // Feature folder boundaries - prevent cross-feature imports
  {
    files: ["packages/frontend/src/features/*/!(_index.ts)"],
    rules: {
      // Enforce that features can only import from:
      // - Their own folder
      // - features/common
      // - hooks, services, types, utils, constants
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: ["@/features/*/!(common)/*"],
              message:
                "Features should not import from other features. Use the common feature for shared code.",
            },
          ],
        },
      ],
    },
  },

  // Enforce API layer usage - prevent direct client usage in components
  {
    files: ["packages/frontend/src/features/*/components/**/*.vue"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          paths: [
            {
              name: "@/services/api-client",
              importNames: ["client"],
              message:
                "Components should not use the API client directly. Use TanStack Query hooks from features/*/queries/ instead.",
            },
          ],
        },
      ],
    },
  },

  // Enforce query layer usage - pages should use queries, not api directly
  {
    files: ["packages/frontend/src/features/*/pages/**/*.vue"],
    rules: {
      "no-restricted-imports": [
        "warn",
        {
          paths: [
            {
              name: "@/services/api-client",
              importNames: ["client"],
              message:
                "Pages should prefer TanStack Query hooks over direct API client usage.",
            },
          ],
        },
      ],
    },
  },
];
