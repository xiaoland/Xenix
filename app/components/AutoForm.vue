<template>
  <a-form
    ref="formRef"
    :model="formData"
    layout="vertical"
    class="auto-form"
  >
    <div v-if="!schema || !schema.properties" class="text-center py-4">
      <a-spin />
      <p class="mt-2">{{ t("common.loading") }}</p>
    </div>
    <div v-else>
      <template
        v-for="(propSchema, propName) in schema.properties"
        :key="propName"
      >
        <a-form-item
          :label="formatFieldLabel(propName as string)"
          :name="propName"
        >
          <template #extra>
            <div class="text-xs text-gray-500">
              {{ propSchema.description || t("tuning.paramGrid.noDescription") }}
            </div>
            <div class="text-xs text-gray-400">
              {{ t("tuning.paramGrid.defaultValue") }}:
              <code class="bg-gray-100 px-1 py-0.5 rounded">{{
                formatDefaultValue(propSchema)
              }}</code>
            </div>
          </template>
          
          <!-- Array input for grid search mode -->
          <ArrayInput
            v-if="mode === 'grid'"
            v-model="formData[propName as string]"
            :item-type="getItemType(propSchema)"
            :placeholder="t('tuning.paramGrid.arrayPlaceholder')"
          />
          
          <!-- Single value inputs for manual mode -->
          <template v-else>
            <!-- Boolean input -->
            <a-switch
              v-if="getItemType(propSchema) === 'boolean'"
              v-model:checked="formData[propName as string]"
            />
            
            <!-- Number/Integer input -->
            <a-input-number
              v-else-if="getItemType(propSchema) === 'number' || getItemType(propSchema) === 'integer'"
              v-model:value="formData[propName as string]"
              :placeholder="formatDefaultValue(propSchema)"
              class="w-full"
            />
            
            <!-- String input -->
            <a-input
              v-else
              v-model:value="formData[propName as string]"
              :placeholder="formatDefaultValue(propSchema)"
            />
          </template>
        </a-form-item>
      </template>
    </div>
  </a-form>
</template>

<script setup lang="ts">
import { ref, computed, watch } from "vue";

const { t } = useI18n();

interface AutoFormProps {
  modelValue: Record<string, any>;
  schema: any;
  mode?: "grid" | "manual"; // grid = arrays for param grid, manual = single values
}

const props = withDefaults(defineProps<AutoFormProps>(), {
  mode: "grid",
});

const emit = defineEmits<{
  "update:modelValue": [value: Record<string, any>];
}>();

const formRef = ref();
const formData = computed({
  get: () => props.modelValue,
  set: (value) => emit("update:modelValue", value),
});

// Initialize form data when schema changes
watch(
  () => props.schema,
  () => {
    if (props.schema) {
      initializeFormData();
    }
  },
  { immediate: true }
);

const initializeFormData = () => {
  const data: Record<string, any> = {};

  if (props.schema && props.schema.properties) {
    for (const [propName, propSchema] of Object.entries(
      props.schema.properties
    )) {
      const schema = propSchema as any;
      
      // Use existing value if available (but not if it's explicitly undefined or null)
      const existingValue = formData.value[propName];
      if (existingValue !== undefined && existingValue !== null) {
        data[propName] = existingValue;
        continue;
      }
      
      // Initialize based on mode and schema
      if (props.mode === "grid") {
        // For grid mode, use arrays
        if (schema.default !== undefined) {
          data[propName] = Array.isArray(schema.default)
            ? [...schema.default]
            : [schema.default];
        } else {
          data[propName] = [];
        }
      } else {
        // For manual mode, use single values
        if (schema.default !== undefined) {
          data[propName] = Array.isArray(schema.default)
            ? schema.default[0]
            : schema.default;
        } else {
          // Create default value based on type
          const itemType = getItemType(schema);
          if (itemType === "boolean") {
            data[propName] = false;
          } else if (itemType === "number" || itemType === "integer") {
            data[propName] = 0;
          } else {
            data[propName] = "";
          }
        }
      }
    }
  }

  formData.value = data;
};

const formatFieldLabel = (fieldName: string): string => {
  // Convert snake_case or camelCase to Title Case
  return fieldName
    .replace(/_/g, " ")
    .replace(/([A-Z])/g, " $1")
    .replace(/^./, (str) => str.toUpperCase())
    .trim();
};

const getItemType = (propSchema: any): string => {
  // Determine the type of the item
  if (propSchema.items) {
    return propSchema.items.type || "string";
  }
  // Direct type (for non-array schemas in manual mode)
  if (propSchema.type && propSchema.type !== "array") {
    return propSchema.type;
  }
  // Try to infer from default values
  if (Array.isArray(propSchema.default) && propSchema.default.length > 0) {
    const firstItem = propSchema.default[0];
    return typeof firstItem;
  }
  if (propSchema.default !== undefined && !Array.isArray(propSchema.default)) {
    return typeof propSchema.default;
  }
  return "string";
};

const formatDefaultValue = (propSchema: any): string => {
  if (propSchema.default !== undefined) {
    if (props.mode === "manual" && Array.isArray(propSchema.default)) {
      // For manual mode, show first value from array
      return JSON.stringify(propSchema.default[0]);
    }
    return JSON.stringify(propSchema.default);
  }
  return "N/A";
};

// Validate form
const validate = async () => {
  return await formRef.value?.validate();
};

// Expose validate method
defineExpose({
  validate,
});
</script>

<style scoped>
.auto-form :deep(.ant-form-item) {
  margin-bottom: 16px;
}

.auto-form :deep(.ant-form-item-label) {
  font-weight: 500;
}
</style>
