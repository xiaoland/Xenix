import { VueQueryPlugin } from "@tanstack/vue-query";
import Antd from "ant-design-vue";
import "ant-design-vue/dist/reset.css";
import { createPinia } from "pinia";
import "uno.css";

import { createApp } from "vue";

import App from "../App.vue";
import i18n, { setupI18n } from "../i18n";
import router from "../routes";

/**
 * Bootstrap the Vue application
 * Handles async initialization (i18n lazy loading) before mounting
 */
export async function bootstrapApp() {
  // Setup i18n with lazy loading
  await setupI18n();

  const app = createApp(App);

  // Install plugins
  app.use(createPinia());
  app.use(router);
  app.use(Antd);
  app.use(i18n);
  app.use(VueQueryPlugin);

  // Mount to DOM
  app.mount("#app");

  return app;
}

/**
 * App initialization entry point
 * Called from main.ts
 */
export function initApp() {
  bootstrapApp().catch((error) => {
    console.error("Failed to bootstrap application:", error);
    // Show user-friendly error message
    const appElement = document.getElementById("app");
    if (appElement) {
      appElement.innerHTML = `
        <div style="padding: 20px; text-align: center;">
          <h1>Application Error</h1>
          <p>Failed to load the application. Please refresh the page or try again later.</p>
        </div>
      `;
    }
  });
}
