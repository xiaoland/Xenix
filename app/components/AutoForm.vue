<template>
  <a-form
    ref="formRef"
    :model="formData"
    layout="vertical"
    class="auto-form"
  >
    <div v-if="!schema || !schema.properties" class="text-center py-4">
      <a-spin />
      <p class="mt-2">{{ t("autoForm.loading") }}</p>
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
              {{ propSchema.description || t("autoForm.noDescription") }}
            </div>
            <div class="text-xs text-gray-400">
              {{ t("autoForm.defaultValue") }}:
              <code class="bg-gray-100 px-1 py-0.5 rounded">{{
                JSON.stringify(getDefaultValue(propSchema))
              }}</code>
            </div>
          </template>

          <!-- Array input for paramGrid mode -->
          <ArrayInput
            v-if="mode === 'paramGrid'"
            v-model="formData[propName as string]"
            :item-type="getArrayItemType(propSchema)"
            :placeholder="t('autoForm.arrayPlaceholder')"
          />

          <!-- Single value inputs for parameters mode -->
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
              :placeholder="getDefaultValue(propSchema).toString()"
              class="w-full"
            />
            <!-- String input -->
            <a-input
              v-else
              v-model:value="formData[propName as string]"
              :placeholder="getDefaultValue(propSchema).toString()"
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
  mode: "paramGrid" | "parameters"; // paramGrid for arrays, parameters for single values
}

const props = defineProps<AutoFormProps>();

const emit = defineEmits<{
  "update:modelValue": [value: Record<string, any>];
}>();

const formRef = ref();
const formData = ref<Record<string, any>>({});

// Helper functions - must be defined before use
const formatFieldLabel = (fieldName: string): string => {
  // Convert snake_case or camelCase to Title Case
  return fieldName
    .replace(/_/g, " ")
    .replace(/([A-Z])/g, " $1")
    .replace(/^./, (str) => str.toUpperCase())
    .trim();
};

const getArrayItemType = (propSchema: any): string => {
  // Determine the type of items in the array
  if (propSchema.items) {
    return propSchema.items.type || "string";
  }
  // Try to infer from default values
  if (Array.isArray(propSchema.default) && propSchema.default.length > 0) {
    const firstItem = propSchema.default[0];
    return typeof firstItem;
  }
  return "string";
};

const getItemType = (propSchema: any): string => {
  // Determine the type of the item (for parameters mode, extract from array schema)
  if (propSchema.items) {
    return propSchema.items.type || "string";
  }
  // Try to infer from default values
  if (Array.isArray(propSchema.default) && propSchema.default.length > 0) {
    const firstItem = propSchema.default[0];
    return typeof firstItem;
  }
  // Fallback to propSchema type if it's directly specified
  if (propSchema.type) {
    return propSchema.type;
  }
  return "string";
};

const getDefaultValue = (propSchema: any): any => {
  if (propSchema.default !== undefined) {
    if (props.mode === "paramGrid") {
      return propSchema.default;
    } else {
      // For parameters mode, show first value from array
      return Array.isArray(propSchema.default)
        ? propSchema.default[0]
        : propSchema.default;
    }
  }
  return "";
};

const initializeFormData = () => {
  const data: Record<string, any> = {};

  if (props.schema && props.schema.properties) {
    for (const [propName, propSchema] of Object.entries(
      props.schema.properties
    )) {
      const schema = propSchema as any;

      // Check if there's a value in modelValue
      if (props.modelValue && props.modelValue[propName] !== undefined) {
        data[propName] = props.modelValue[propName];
      } else if (schema.default !== undefined) {
        // Use schema defaults based on mode
        if (props.mode === "paramGrid") {
          // For paramGrid mode, expect arrays
          data[propName] = Array.isArray(schema.default)
            ? [...schema.default]
            : [schema.default];
        } else {
          // For parameters mode, extract single values
          data[propName] = Array.isArray(schema.default)
            ? schema.default[0]
            : schema.default;
        }
      } else {
        // Create default value based on mode and type
        if (props.mode === "paramGrid") {
          data[propName] = [];
        } else {
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

// Initialize form data when schema or initial values change
watch(
  () => [props.modelValue, props.schema, props.mode],
  () => {
    if (props.schema) {
      initializeFormData();
    }
  },
  { immediate: true, deep: true }
);

// Emit changes to parent
watch(
  formData,
  (newValue) => {
    emit("update:modelValue", newValue);
  },
  { deep: true }
);

const validate = async () => {
  return await formRef.value?.validate();
};

const getValues = () => {
  return formData.value;
};

defineExpose({
  validate,
  getValues,
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
