<template>
  <a-form
    ref="formRef"
    :model="formData"
    layout="vertical"
    class="model-param-form"
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

          <!-- Boolean input -->
          <a-switch
            v-if="getItemType(propSchema) === 'boolean'"
            v-model:checked="formData[propName as string]"
          />
          <!-- Number/Integer input -->
          <a-input-number
            v-else-if="getItemType(propSchema) === 'number' || getItemType(propSchema) === 'integer'"
            v-model:value="formData[propName as string]"
            class="w-full"
            :precision="getItemType(propSchema) === 'integer' ? 0 : undefined"
          />
          <!-- String input -->
          <a-input
            v-else
            v-model:value="formData[propName as string]"
            :placeholder="t('autoForm.enterValue')"
          />
        </a-form-item>
      </template>
    </div>
  </a-form>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import { ModelService } from "~/services";

const { t } = useI18n();

const props = defineProps<{
  model: string;
  modelValue?: Record<string, any>;
}>();

const emit = defineEmits<{
  "update:modelValue": [value: Record<string, any>];
}>();

const formRef = ref();
const formData = ref<Record<string, any>>({});
const modelMetadata = ref<any>(null);

// Computed schema from model metadata  
const schema = computed(() => {
  return modelMetadata.value?.paramSchema || null;
});

// Fetch model metadata
const fetchModelMetadata = async () => {
  try {
    const response = await ModelService.fetchMetadata();
    if (response.success && response.models) {
      const metadata = response.models.find((m: any) => m.name === props.model);
      if (metadata) {
        modelMetadata.value = metadata;
      }
    }
  } catch (error) {
    console.error(`Failed to fetch metadata for ${props.model}:`, error);
  }
};

// Initialize form data
const initializeFormData = () => {
  const data: Record<string, any> = {};

  if (schema.value && schema.value.properties) {
    for (const [propName, propSchema] of Object.entries(
      schema.value.properties
    )) {
      const sch = propSchema as any;
      // Use modelValue if provided, otherwise use schema defaults
      if (props.modelValue && props.modelValue[propName] !== undefined) {
        data[propName] = props.modelValue[propName];
      } else if (sch.default !== undefined) {
        // For manual tuning, convert array to single value
        data[propName] = Array.isArray(sch.default)
          ? sch.default[0]
          : sch.default;
      } else {
        // Create default value based on type
        const itemType = getItemType(sch);
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

  formData.value = data;
};

// Watch for changes in formData and emit
watch(
  formData,
  (newVal) => {
    emit("update:modelValue", newVal);
  },
  { deep: true }
);

// Watch for schema or modelValue changes
watch(
  () => [schema.value, props.modelValue],
  () => {
    if (schema.value) {
      initializeFormData();
    }
  },
  { immediate: true }
);

// Format field label
const formatFieldLabel = (name: string) => {
  return name
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
};

// Get item type
const getItemType = (propSchema: any): string => {
  // Determine the type of the item (for manual tuning, we extract from array schema)
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

// Get default value
const getDefaultValue = (propSchema: any): any => {
  if (propSchema.default !== undefined) {
    return Array.isArray(propSchema.default)
      ? propSchema.default[0]
      : propSchema.default;
  }
  const itemType = getItemType(propSchema);
  if (itemType === "boolean") return false;
  if (itemType === "number" || itemType === "integer") return 0;
  return "";
};

// Validate form
const validate = async () => {
  return await formRef.value?.validate();
};

// Expose validate method
defineExpose({
  validate,
});

// Initialize
onMounted(() => {
  fetchModelMetadata();
});
</script>

<style scoped>
.model-param-form {
  max-height: 500px;
  overflow-y: auto;
}
</style>
