<template>
  <div class="flex justify-between items-center mb-6">
    <div class="flex gap-4">
      <NuxtLink to="/">
        <a-button
          type="text"
          size="large"
          :class="[
            { 'bg-blue-50': isCurrentRoute('/') },
            'inline-flex items-center',
          ]"
        >
          <template #icon><span class="i-mdi-home" /></template>
          {{ $t("navigation.home") }}
        </a-button>
      </NuxtLink>

      <NuxtLink to="/datasets">
        <a-button
          type="text"
          size="large"
          :class="[
            { 'bg-blue-50': isCurrentRoute('/datasets') },
            'inline-flex items-center',
          ]"
        >
          <template #icon><span class="i-mdi-database" /></template>
          {{ $t("navigation.datasets") }}
        </a-button>
      </NuxtLink>

      <NuxtLink to="/python-env">
        <a-button
          type="text"
          size="large"
          :class="[
            { 'bg-blue-50': isCurrentRoute('/python-env') },
            'inline-flex items-center',
          ]"
        >
          <template #icon><span class="i-mdi-snake" /></template>
          {{ $t("navigation.pythonEnv") }}
        </a-button>
      </NuxtLink>
    </div>

    <LanguageSwitcher />
  </div>
</template>

<script setup lang="ts">
import { useRoute } from "vue-router";

const route = useRoute();

const isCurrentRoute = (path: string) => {
  return route.path === path;
};
</script>
