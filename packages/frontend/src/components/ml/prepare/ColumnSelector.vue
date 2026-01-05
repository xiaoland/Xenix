<template>
  <div class="space-y-6">
    <!-- Feature Columns Selection -->
    <div>
      <label class="block text-sm font-medium mb-2">
        Feature Columns <span class="text-red-500">*</span>
      </label>
      <p class="text-sm text-gray-600 mb-3">
        Select the columns that will be used as input features for the model.
      </p>
      <a-select
        v-model:value="localFeatureColumns"
        mode="multiple"
        placeholder="Select feature columns"
        :options="availableFeatureOptions"
        class="w-full"
        @change="handleFeatureColumnsChange"
      />
      <p class="text-xs text-gray-500 mt-1">
        Selected: {{ localFeatureColumns.length }} column(s)
      </p>
    </div>

    <!-- Target Column Selection -->
    <div>
      <label class="block text-sm font-medium mb-2">
        Target Column <span class="text-red-500">*</span>
      </label>
      <p class="text-sm text-gray-600 mb-3">
        Select the column that the model should predict.
      </p>
      <a-select
        v-model:value="localTargetColumn"
        placeholder="Select target column"
        :options="availableTargetOptions"
        class="w-full"
        @change="handleTargetColumnChange"
      />
    </div>

    <!-- Summary -->
    <div v-if="localFeatureColumns.length > 0 && localTargetColumn" class="bg-blue-50 border border-blue-200 rounded p-4">
      <h4 class="font-medium mb-2">Configuration Summary:</h4>
      <ul class="text-sm space-y-1">
        <li><strong>Features:</strong> {{ localFeatureColumns.join(', ') }}</li>
        <li><strong>Target:</strong> {{ localTargetColumn }}</li>
      </ul>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue';

const props = defineProps<{
  columns: string[];
  featureColumns: string[];
  targetColumn?: string;
}>();

const emit = defineEmits<{
  'update:featureColumns': [value: string[]];
  'update:targetColumn': [value: string];
}>();

const localFeatureColumns = ref<string[]>([...props.featureColumns]);
const localTargetColumn = ref<string | undefined>(props.targetColumn);

// Available feature columns (exclude target if selected)
const availableFeatureOptions = computed(() => {
  return props.columns
    .filter(col => col !== localTargetColumn.value)
    .map(col => ({ label: col, value: col }));
});

// Available target columns (exclude selected features)
const availableTargetOptions = computed(() => {
  return props.columns
    .filter(col => !localFeatureColumns.value.includes(col))
    .map(col => ({ label: col, value: col }));
});

const handleFeatureColumnsChange = () => {
  emit('update:featureColumns', localFeatureColumns.value);
};

const handleTargetColumnChange = () => {
  if (localTargetColumn.value) {
    emit('update:targetColumn', localTargetColumn.value);
  }
};

// Watch for external changes
watch(() => props.featureColumns, (newVal) => {
  localFeatureColumns.value = [...newVal];
});

watch(() => props.targetColumn, (newVal) => {
  localTargetColumn.value = newVal;
});
</script>
