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
import { computed, ref } from 'vue';
import { useI18n } from 'vue-i18n';

import { loadLanguageAsync, SUPPORT_LOCALES } from '../../i18n';

const { locale } = useI18n();
const isLoading = ref(false);

const currentLocale = computed({
  get: () => locale.value,
  set: (value) => {
    locale.value = value;
  },
});

const languageOptions = [
  { value: 'en', label: 'English' },
  { value: 'zh-CN', label: '中文' },
];

const handleLanguageChange = async (lang: string) => {
  if (!SUPPORT_LOCALES.includes(lang as any)) {
    console.error(`Unsupported language: ${lang}`);
    return;
  }

  isLoading.value = true;
  try {
    await loadLanguageAsync(lang);
    // Store the selected language in localStorage for persistence
    localStorage.setItem('xenix-locale', lang);
  } catch (error) {
    console.error('Failed to change language:', error);
  } finally {
    isLoading.value = false;
  }
};
</script>

<style scoped>
/* Styles handled by Ant Design */
</style>
