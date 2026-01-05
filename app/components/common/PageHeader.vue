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

    <div class="flex items-center gap-4">
      <LanguageSwitcher />
      <div v-if="authStore.isAuthenticated" class="flex items-center gap-2">
        <span>{{ authStore.user?.email }}</span>
        <a-button @click="authStore.logout" type="text" size="large">
          {{ $t("auth.logout") }}
        </a-button>
      </div>
      <NuxtLink v-else to="/signin">
        <a-button type="text" size="large">
          {{ $t("auth.signin.title") }}
        </a-button>
      </NuxtLink>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRoute } from "vue-router";
import LanguageSwitcher from "./LanguageSwitcher.vue";
import { useAuthStore } from "~/stores/auth";

const route = useRoute();
const authStore = useAuthStore();

const isCurrentRoute = (path: string) => {
  return route.path === path;
};
</script>
