<template>
  <div class="bg-gray-900 rounded-lg p-4 max-h-96 overflow-y-auto">
    <div v-if="logs && logs.length > 0">
      <div
        v-for="log in formattedLogs"
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
        <!-- Show additional attributes if present -->
        <div v-if="log.extraInfo" class="ml-8 mt-1 text-xs text-gray-400">
          {{ log.extraInfo }}
        </div>
      </div>
    </div>
    <div v-else class="text-gray-500 text-center py-4">
      {{ $t("logs.noLogs") }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{
  logs: any[];
}>();

// Format logs to be human-friendly
const formattedLogs = computed(() => {
  if (!props.logs) return [];
  
  return props.logs.map((log) => {
    let message = log.message || log.body || "";
    let extraInfo = "";
    
    // Try to extract structured information from attributes
    if (log.attributes) {
      try {
        const attrs = typeof log.attributes === 'string' 
          ? JSON.parse(log.attributes) 
          : log.attributes;
        
        // Format logger name if present
        if (attrs.logger_name) {
          message = `[${attrs.logger_name}] ${message}`;
        }
        
        // Format additional attributes
        const relevantAttrs = Object.entries(attrs)
          .filter(([key]) => key !== 'logger_name')
          .map(([key, value]) => `${key}: ${JSON.stringify(value)}`)
          .join(', ');
        
        if (relevantAttrs) {
          extraInfo = relevantAttrs;
        }
      } catch (e) {
        // If parsing fails, use as-is
      }
    }
    
    return {
      id: log.id,
      timestamp: log.timestamp,
      severity: log.severity || log.severityText || 'INFO',
      message,
      extraInfo,
    };
  });
});

const formatTimestamp = (timestamp: number) => {
  // Convert nanoseconds to milliseconds
  const date = new Date(timestamp / 1000000);
  return date.toLocaleTimeString();
};
</script>
