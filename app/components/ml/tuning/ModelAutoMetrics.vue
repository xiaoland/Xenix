<template>
  <div class="model-auto-metrics">
    <template v-if="!metrics || Object.keys(metrics).length === 0">
      <span class="text-gray-400">{{ t("common.noData") }}</span>
    </template>
    <template v-else>
      <div class="overflow-x-auto">
        <div class="flex gap-2 whitespace-nowrap min-w-max">
          <template v-for="(value, key) in metrics" :key="key">
            <div class="metric-item">
              <span class="metric-label"
                >{{ formatMetricLabel(key as string) }}:</span
              >
              <span class="metric-value">{{ formatMetricValue(value) }}</span>
            </div>
          </template>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";

const { t } = useI18n();

const props = defineProps<{
  metrics: Record<string, any> | undefined;
}>();

// Format metric label (e.g., "mse_train" -> "MSE Train")
const formatMetricLabel = (key: string): string => {
  return key
    .split("_")
    .map((word) => word.toUpperCase())
    .join(" ");
};

// Format metric value based on type
const formatMetricValue = (value: any): string => {
  if (value === null || value === undefined) {
    return t("common.na");
  }

  if (typeof value === "number") {
    // Format numbers to reasonable precision
    if (Number.isInteger(value)) {
      return value.toString();
    }
    // For floating point, show up to 6 decimal places, removing trailing zeros
    return value.toFixed(6).replace(/\.?0+$/, "");
  }

  if (typeof value === "boolean") {
    return value ? t("common.yes") : t("common.no");
  }

  if (typeof value === "string") {
    return value;
  }

  if (Array.isArray(value)) {
    return `[${value.map(formatMetricValue).join(", ")}]`;
  }

  if (typeof value === "object") {
    // For nested objects, show as JSON
    return JSON.stringify(value);
  }

  return String(value);
};
</script>

<style scoped>
.model-auto-metrics {
  font-size: 0.875rem;
}

.metric-item {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.25rem 0.5rem;
  background-color: #f3f4f6;
  border-radius: 0.25rem;
}

.metric-label {
  font-weight: 500;
  color: #6b7280;
}

.metric-value {
  color: #111827;
  font-family: monospace;
}
</style>
