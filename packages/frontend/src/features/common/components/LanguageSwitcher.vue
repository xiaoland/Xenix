<template>
  <a-select
    v-model:value="currentLocale"
    :options="languageOptions"
    :loading="isLoading"
    style="width: 120px"
    @change="handleLanguageChange"
  >
    <template #suffixIcon>
      <span class="i-mdi-translate" />
    </template>
  </a-select>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";

import {
  LOCALE_STORAGE_KEY,
  loadLanguageAsync,
  SUPPORT_LOCALES,
  type SupportedLocale,
} from "@/i18n";

const { locale } = useI18n();
const isLoading = ref(false);

const currentLocale = computed({
  get: () => locale.value,
  set: (value) => {
    locale.value = value;
  },
});

const languageOptions = [
  { value: "en", label: "English" },
  { value: "zh-CN", label: "中文" },
];

/**
 * Type guard to check if a string is a valid locale
 */
function isSupportedLocale(locale: string): locale is SupportedLocale {
  return SUPPORT_LOCALES.includes(locale as SupportedLocale);
}

const handleLanguageChange = async (lang: string) => {
  if (!isSupportedLocale(lang)) {
    console.error(`Unsupported language: ${lang}`);
    return;
  }

  isLoading.value = true;
  try {
    await loadLanguageAsync(lang);
    // Store the selected language in localStorage for persistence
    localStorage.setItem(LOCALE_STORAGE_KEY, lang);
  } catch (error) {
    console.error("Failed to change language:", error);
  } finally {
    isLoading.value = false;
  }
};
</script>

<style scoped>
/* Styles handled by Ant Design */
</style>
