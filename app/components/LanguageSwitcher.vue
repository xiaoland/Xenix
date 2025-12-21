<template>
  <a-dropdown>
    <a-button>
      <i class="i-mdi-translate mr-2"></i>
      {{ currentLocaleName }}
      <i class="i-mdi-chevron-down ml-2"></i>
    </a-button>
    <template #overlay>
      <a-menu @click="handleLocaleChange">
        <a-menu-item
          v-for="locale in availableLocales"
          :key="locale.code"
          :class="{ 'ant-menu-item-selected': locale.code === currentLocale }"
        >
          {{ locale.name }}
        </a-menu-item>
      </a-menu>
    </template>
  </a-dropdown>
</template>

<script setup lang="ts">
import { computed } from 'vue';

const { locale, locales, setLocale } = useI18n();

const availableLocales = computed(() => locales.value);

const currentLocale = computed(() => locale.value);

const currentLocaleName = computed(() => {
  const current = availableLocales.value.find((l: any) => l.code === currentLocale.value);
  return current?.name || currentLocale.value;
});

const handleLocaleChange = async ({ key }: { key: string }) => {
  await setLocale(key);
};
</script>
