/**
 * Global Application Context
 *
 * Provides access to the Vue app instance for debugging and advanced use cases.
 * Note: Prefer dependency injection over global context in production code.
 */

import type { App } from "vue";
import type { Router } from "vue-router";
import type { I18n } from "vue-i18n";
import type { Pinia } from "pinia";

/**
 * Global application context
 * Available for debugging and advanced use cases
 */
export interface AppContext {
  app: App;
  router: Router;
  pinia: Pinia;
  i18n: I18n;
}

/**
 * Global app instance (set after bootstrap)
 * Use with caution - prefer dependency injection
 */
declare global {
  interface Window {
    __VUE_APP__?: AppContext;
  }
}

/**
 * Set global app context for debugging
 */
export function setGlobalAppContext(context: AppContext) {
  if (import.meta.env.DEV) {
    window.__VUE_APP__ = context;
  }
}

/**
 * Get global app context
 * Only available in development mode
 */
export function getGlobalAppContext(): AppContext | undefined {
  return window.__VUE_APP__;
}
