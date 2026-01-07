import { createI18n } from 'vue-i18n';

// Supported locales
export const SUPPORT_LOCALES = ['en', 'zh-CN'] as const;
export type SupportedLocale = (typeof SUPPORT_LOCALES)[number];

// LocalStorage key for language preference
export const LOCALE_STORAGE_KEY = 'xenix-locale';

// Track loaded languages
const loadedLanguages: string[] = [];

// Create i18n instance with empty messages initially
const i18n = createI18n({
  legacy: false,
  locale: 'en',
  fallbackLocale: 'en',
  messages: {},
});

/**
 * Type guard to check if a string is a valid locale
 */
function isSupportedLocale(locale: string): locale is SupportedLocale {
  return SUPPORT_LOCALES.includes(locale as SupportedLocale);
}

/**
 * Get the base URL for locale files
 * In production, this could point to a CDN
 */
function getLocaleBaseUrl(): string {
  // Use environment variable if available, otherwise default to /locales/
  return import.meta.env.VITE_LOCALE_BASE_URL || '/locales/';
}

/**
 * Load language async from remote source and set as current locale
 * Supports remote/CDN loading for over-the-air translation updates
 * @param lang - Language code to load (e.g., 'en', 'zh-CN')
 */
export async function loadLanguageAsync(lang: string): Promise<void> {
  // Validate locale
  if (!isSupportedLocale(lang)) {
    console.error(`Unsupported locale: ${lang}`);
    return;
  }

  // If language is already loaded, just switch to it
  if (loadedLanguages.includes(lang)) {
    i18n.global.locale.value = lang;
    return;
  }

  // Load the language from remote source (server or CDN)
  try {
    const baseUrl = getLocaleBaseUrl();
    const localeUrl = `${baseUrl}${lang}.json`;
    
    console.log(`Loading locale from remote: ${localeUrl}`);
    
    const response = await fetch(localeUrl);
    if (!response.ok) {
      throw new Error(`Failed to fetch locale: ${response.status} ${response.statusText}`);
    }
    
    const messages = await response.json();
    i18n.global.setLocaleMessage(lang, messages);
    loadedLanguages.push(lang);
    i18n.global.locale.value = lang;
    
    console.log(`Successfully loaded locale: ${lang}`);
  } catch (error) {
    console.error(`Failed to load language '${lang}':`, error);
    throw error;
  }
}

/**
 * Get saved language preference from localStorage
 */
function getSavedLocale(): SupportedLocale | null {
  if (typeof window === 'undefined') return null;
  
  const saved = localStorage.getItem(LOCALE_STORAGE_KEY);
  return saved && isSupportedLocale(saved) ? saved : null;
}

// Load the initial language (saved preference or English)
export async function setupI18n(): Promise<typeof i18n> {
  const savedLocale = getSavedLocale();
  const initialLocale = savedLocale || 'en';
  await loadLanguageAsync(initialLocale);
  return i18n;
}

export default i18n;
