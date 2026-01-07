import { createI18n } from 'vue-i18n';

// Supported locales
export const SUPPORT_LOCALES = ['en', 'zh-CN'] as const;
export type SupportedLocale = (typeof SUPPORT_LOCALES)[number];

// Track loaded languages
const loadedLanguages: string[] = ['en'];

// Create i18n instance with only English initially
const i18n = createI18n({
  legacy: false,
  locale: 'en',
  fallbackLocale: 'en',
  messages: {
    en: {},
  },
});

/**
 * Load language async and set as current locale
 * @param lang - Language code to load (e.g., 'en', 'zh-CN')
 */
export async function loadLanguageAsync(lang: string): Promise<void> {
  // If language is already loaded, just switch to it
  if (loadedLanguages.includes(lang)) {
    i18n.global.locale.value = lang as any;
    return;
  }

  // Load the language module dynamically
  try {
    const messages = await import(`../locales/${lang}.json`);
    i18n.global.setLocaleMessage(lang, messages.default);
    loadedLanguages.push(lang);
    i18n.global.locale.value = lang as any;
  } catch (error) {
    console.error(`Failed to load language '${lang}':`, error);
    throw error;
  }
}

// Load the initial language (English)
export async function setupI18n(): Promise<typeof i18n> {
  await loadLanguageAsync('en');
  return i18n;
}

export default i18n;
