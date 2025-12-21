<template>
  <div class="flex justify-between items-center mb-6">
    <div class="flex gap-4">
      <NuxtLink to="/">
        <a-button 
          type="text" 
          size="large"
          :class="{ 'bg-blue-50': isCurrentRoute('/') }"
        >
          <template #icon><i class="i-mdi-home"></i></template>
          {{ $t('navigation.home') }}
        </a-button>
      </NuxtLink>
      
      <NuxtLink to="/datasets">
        <a-button 
          type="text" 
          size="large"
          :class="{ 'bg-blue-50': isCurrentRoute('/datasets') }"
        >
          <template #icon><i class="i-mdi-database"></i></template>
          {{ $t('navigation.datasets') }}
        </a-button>
      </NuxtLink>
    </div>

    <LanguageSwitcher />
  </div>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router';

const route = useRoute();

const isCurrentRoute = (path: string) => {
  return route.path === path;
};
</script>
