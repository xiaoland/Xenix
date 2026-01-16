<template>
  <div class="model-param-form">
    <a-spin :spinning="loading">
      <div v-if="paramSchema && Object.keys(paramSchema).length > 0">
        <a-form layout="vertical">
          <a-form-item
            v-for="(schema, key) in paramSchema"
            :key="key"
            :label="formatLabel(key)"
          >
            <!-- Number input -->
            <a-input-number
              v-if="schema.type === 'number' || schema.type === 'integer'"
              v-model:value="localValue[key]"
              :min="schema.minimum"
              :max="schema.maximum"
              :step="schema.type === 'integer' ? 1 : 0.01"
              style="width: 100%"
              :placeholder="schema.description || `Enter ${formatLabel(key)}`"
            />

            <!-- Boolean input -->
            <a-switch
              v-else-if="schema.type === 'boolean'"
              v-model:checked="localValue[key]"
            />

            <!-- Enum/Select input -->
            <a-select
              v-else-if="schema.enum && schema.enum.length > 0"
              v-model:value="localValue[key]"
              :placeholder="schema.description || `Select ${formatLabel(key)}`"
              style="width: 100%"
            >
              <a-select-option
                v-for="option in schema.enum"
                :key="option"
                :value="option"
              >
                {{ option }}
              </a-select-option>
            </a-select>

            <!-- String input (default) -->
            <a-input
              v-else
              v-model:value="localValue[key]"
              :placeholder="schema.description || `Enter ${formatLabel(key)}`"
            />

            <div v-if="schema.description" class="text-xs text-gray-500 mt-1">
              {{ schema.description }}
            </div>
          </a-form-item>
        </a-form>
      </div>
      <div v-else class="text-gray-500 text-center py-4">
        No parameters available for this model
      </div>
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from "vue";
import { client } from "../../../api/client";

interface ParamSchema {
  type: string;
  description?: string;
  minimum?: number;
  maximum?: number;
  enum?: any[];
  default?: any;
}

const props = defineProps<{
  model: string;
  modelValue?: Record<string, any>;
}>();

const emit = defineEmits<{
  "update:modelValue": [value: Record<string, any>];
}>();

const loading = ref(false);
const paramSchema = ref<Record<string, ParamSchema>>({});
const localValue = ref<Record<string, any>>({});

// Fetch model parameter schema
const fetchModelSchema = async () => {
  if (!props.model) return;

  loading.value = true;
  try {
    const response = await client.models[":id"].$get({
      param: { id: props.model },
    });
    if (response.ok) {
      const data = await response.json();
      if (data.paramSchema) {
        paramSchema.value = data.paramSchema;
        // Initialize with default values
        initializeValues();
      }
    }
  } catch (error) {
    console.error("Failed to fetch model schema:", error);
  } finally {
    loading.value = false;
  }
};

// Initialize form values with defaults or existing values
const initializeValues = () => {
  const newValue: Record<string, any> = {};

  // Use provided modelValue if available
  if (props.modelValue) {
    Object.assign(newValue, props.modelValue);
  }

  // Fill in defaults for missing values
  Object.entries(paramSchema.value).forEach(([key, schema]) => {
    if (!(key in newValue) && schema.default !== undefined) {
      newValue[key] = schema.default;
    }
  });

  localValue.value = newValue;
  emit("update:modelValue", newValue);
};

// Format label from camelCase/snake_case to Title Case
const formatLabel = (key: string): string => {
  return key
    .replace(/_/g, " ")
    .replace(/([A-Z])/g, " $1")
    .trim()
    .split(" ")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
};

// Watch for changes in local value
watch(
  localValue,
  (newValue) => {
    emit("update:modelValue", newValue);
  },
  { deep: true }
);

// Watch for model changes
watch(
  () => props.model,
  () => {
    fetchModelSchema();
  },
  { immediate: true }
);

// Expose validate method for parent component
defineExpose({
  validate: () => Promise.resolve(true), // Simple validation, can be enhanced
});

onMounted(() => {
  if (props.model) {
    fetchModelSchema();
  }
});
</script>

<style scoped>
.model-param-form {
  max-height: 500px;
  overflow-y: auto;
}
</style>
