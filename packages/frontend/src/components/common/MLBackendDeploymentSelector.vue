<template>
  <div class="ml-backend-deployment-selector">
    <label class="label">ML Backend Deployment</label>
    <div class="select-wrapper">
      <select
        :value="modelValue"
        @change="handleChange"
        class="select"
        :disabled="disabled || isLoading"
      >
        <option :value="null">Select ML Backend Deployment</option>
        <option
          v-for="deployment in filteredDeployments"
          :key="deployment.id"
          :value="deployment.id"
        >
          {{ deployment.name }} ({{ deployment.storage }})
        </option>
      </select>

      <span v-if="isLoading" class="loading-indicator">Loading...</span>
      <span v-else-if="error" class="error-message">Failed to load deployments</span>
      <span v-else-if="datasetStorage && filteredDeployments.length === 0" class="info-message">
        No {{ datasetStorage }} deployments available
      </span>
    </div>

    <p v-if="modelValue && selectedDeployment" class="help-text">
      Selected: {{ selectedDeployment.name }}
      <span v-if="selectedDeployment.apiUrl" class="api-url">
        ({{ selectedDeployment.apiUrl }})
      </span>
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { MLBackendDeployment } from '@xenix/shared';
import { useMLBackendDeployments } from '@/composables';

interface Props {
  modelValue?: number | null;
  datasetStorage?: 'local' | 'oss' | null;
  disabled?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: null,
  datasetStorage: null,
  disabled: false,
});

const emit = defineEmits<{
  'update:modelValue': [value: number | null];
}>();

const { data: deployments, isLoading, error } = useMLBackendDeployments();

const filteredDeployments = computed(() => {
  if (!deployments.value) return [];

  if (!props.datasetStorage) {
    return deployments.value;
  }

  return deployments.value.filter(
    (deployment: MLBackendDeployment) => deployment.storage === props.datasetStorage
  );
});

const selectedDeployment = computed(() => {
  if (!props.modelValue || !deployments.value) return null;
  return deployments.value.find((d: MLBackendDeployment) => d.id === props.modelValue) || null;
});

function handleChange(event: Event) {
  const target = event.target as HTMLSelectElement;
  const value = target.value === '' || target.value === 'null' ? null : Number(target.value);
  emit('update:modelValue', value);
}
</script>

<style scoped>
.ml-backend-deployment-selector {
  margin-bottom: 1.5rem;
}

.label {
  display: block;
  font-weight: 600;
  margin-bottom: 0.5rem;
  color: #374151;
}

.select-wrapper {
  position: relative;
}

.select {
  width: 100%;
  padding: 0.5rem 0.75rem;
  border: 1px solid #d1d5db;
  border-radius: 0.375rem;
  font-size: 0.875rem;
  background-color: white;
  cursor: pointer;
  transition: border-color 0.2s;
}

.select:hover:not(:disabled) {
  border-color: #9ca3af;
}

.select:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.select:disabled {
  background-color: #f3f4f6;
  cursor: not-allowed;
  opacity: 0.6;
}

.loading-indicator,
.error-message,
.info-message {
  display: block;
  margin-top: 0.25rem;
  font-size: 0.75rem;
}

.loading-indicator {
  color: #6b7280;
}

.error-message {
  color: #ef4444;
}

.info-message {
  color: #3b82f6;
}

.help-text {
  margin-top: 0.5rem;
  font-size: 0.75rem;
  color: #6b7280;
}

.api-url {
  color: #9ca3af;
  font-family: monospace;
}
</style>
