// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: "2025-07-15",
  devtools: { enabled: true },
  modules: ["@unocss/nuxt", "@ant-design-vue/nuxt", "@nuxtjs/i18n"],
  devServer: {
    port: 3005,
  },
  vite: {
    optimizeDeps: {
      include: ["xlsx"],
    },
  },
  nitro: {
    externals: {
      inline: ["xlsx"],
    },
  },
  antd: {},
  i18n: {
    locales: [
      {
        code: "en",
        name: "English",
        file: "en.json",
        iso: "en-US",
      },
      {
        code: "zh-CN",
        name: "简体中文",
        file: "zh-CN.json",
        iso: "zh-CN",
      },
    ],
    lazy: true,
    langDir: "locales",
    defaultLocale: "en",
    fallbackLocale: "en",
    strategy: "no_prefix",
    detectBrowserLanguage: {
      useCookie: true,
      cookieKey: "i18n_redirected",
      redirectOn: "root",
      alwaysRedirect: false,
      fallbackLocale: "en",
    },
  },
});
