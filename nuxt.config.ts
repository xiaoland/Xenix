// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: "2025-07-15",
  devtools: { enabled: true },
  modules: ["@unocss/nuxt", "@ant-design-vue/nuxt", "@ant-design-vue/nuxt"],
  devServer: {
    port: 3005,
  },
  antd: {},
});
