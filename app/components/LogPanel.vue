<template>
  <div class="bg-gray-900 rounded-lg p-4 max-h-96 overflow-y-auto">
    <div v-if="logs && logs.length > 0">
      <div
        v-for="log in logs"
        :key="log.id"
        class="mb-2 font-mono text-sm"
        :class="{
          'text-gray-400': log.severity === 'DEBUG',
          'text-white': log.severity === 'INFO',
          'text-yellow-400': log.severity === 'WARNING',
          'text-red-400': log.severity === 'ERROR',
          'text-red-600': log.severity === 'CRITICAL',
        }"
      >
        <span class="text-gray-500"
          >[{{ formatTimestamp(log.timestamp) }}]</span
        >
        <span class="font-bold ml-2">[{{ log.severity }}]</span>
        <span class="ml-2">{{ log.message }}</span>
      </div>
    </div>
    <div v-else class="text-gray-500 text-center py-4">
      {{ $t("logs.noLogs") }}
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  logs: any[];
}>();

const formatTimestamp = (timestamp: number) => {
  // Convert nanoseconds to milliseconds
  const date = new Date(timestamp / 1000000);
  return date.toLocaleTimeString();
};
</script>
