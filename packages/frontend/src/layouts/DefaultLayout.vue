<template>
  <div class="app-layout min-h-screen bg-gray-50">
    <header class="bg-white shadow-sm border-b border-gray-200">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-4">
            <router-link to="/" class="text-2xl font-bold text-blue-600">
              Xenix
            </router-link>
            <span class="text-sm text-gray-500">ML Training Platform</span>
          </div>

          <div class="flex items-center gap-4">
            <router-link
              to="/"
              class="text-gray-700 hover:text-blue-600 transition-colors"
            >
              Projects
            </router-link>

            <router-link
              to="/tasks"
              class="text-gray-700 hover:text-blue-600 transition-colors"
            >
              Tasks
            </router-link>

            <a-button
              v-if="isAuthenticated"
              type="text"
              danger
              class="inline-flex items-center"
              @click="handleLogout"
            >
              <span class="i-mdi-logout mr-1" />
              Logout
            </a-button>
          </div>
        </div>
      </div>
    </header>

    <main class="py-8">
      <slot />
    </main>

    <footer class="bg-white border-t border-gray-200 mt-auto">
      <div
        class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 text-center text-sm text-gray-500"
      >
        © 2026 Xenix ML Platform
      </div>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';

import { useAuthStore } from '../stores/auth';

const authStore = useAuthStore();

const isAuthenticated = computed(() => authStore.isAuthenticated);

const handleLogout = () => {
  authStore.logout();
};
</script>

<style scoped>
.app-layout {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

main {
  flex: 1;
}
</style>
