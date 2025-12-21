<template>
  <div>
    <h3 class="text-lg font-medium mb-3">Available Models for Tuning</h3>
    <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
      <a-button
        v-for="model in availableModels"
        :key="model.value"
        :type="selectedModels.includes(model.value) ? 'primary' : 'default'"
        @click="toggleModel(model.value)"
        class="h-auto py-3"
      >
        <div class="text-center">
          <div class="font-medium">{{ model.label }}</div>
          <div v-if="tuningStatus[model.value]" class="text-xs mt-1">
            <a-tag :color="getStatusColor(tuningStatus[model.value])">
              {{ tuningStatus[model.value] }}
            </a-tag>
          </div>
        </div>
      </a-button>
    </div>
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{
  availableModels: Array<{ label: string; value: string }>;
  tuningStatus: Record<string, string>;
}>();

const selectedModels = defineModel<string[]>({ required: true });

const emit = defineEmits<{
  toggle: [modelValue: string]
}>();

const toggleModel = (modelValue: string) => {
  const index = selectedModels.value.indexOf(modelValue);
  if (index > -1) {
    selectedModels.value.splice(index, 1);
  } else {
    selectedModels.value.push(modelValue);
  }
  emit('toggle', modelValue);
};

const getStatusColor = (status: string) => {
  switch (status) {
    case 'completed':
      return 'green';
    case 'running':
      return 'blue';
    case 'failed':
      return 'red';
    default:
      return 'default';
  }
};
</script>
