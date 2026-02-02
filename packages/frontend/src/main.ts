import { VueQueryPlugin } from "@tanstack/vue-query";
import Antd from "ant-design-vue";
import "ant-design-vue/dist/reset.css";
import { createPinia } from "pinia";
import "uno.css";

import { createApp } from "vue";

import App from "./App.vue";
import i18n, { setupI18n } from "./i18n";
import router from "./routes";

// Setup i18n with lazy loading
setupI18n().then(() => {
  const app = createApp(App);

  app.use(createPinia());
  app.use(router);
  app.use(Antd);
  app.use(i18n);
  app.use(VueQueryPlugin);

  app.mount("#app");
});
