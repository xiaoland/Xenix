<template>
  <a-form
    ref="formRef"
    :model="formData"
    layout="vertical"
    class="model-param-grid-form"
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
                JSON.stringify(propSchema.default || [])
              }}</code>
            </div>
          </template>

          <!-- Array input for paramGrid mode -->
          <ArrayInput
            v-model="formData[propName as string]"
            :item-type="getArrayItemType(propSchema)"
            :placeholder="t('autoForm.arrayPlaceholder')"
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
  return modelMetadata.value?.paramGridSchema || null;
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
        data[propName] = Array.isArray(sch.default)
          ? [...sch.default]
          : sch.default;
      } else {
        // Create empty array as fallback
        data[propName] = [];
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

// Get array item type
const getArrayItemType = (propSchema: any): string => {
  if (propSchema.items && propSchema.items.type) {
    return propSchema.items.type;
  }
  if (Array.isArray(propSchema.default) && propSchema.default.length > 0) {
    const firstItem = propSchema.default[0];
    return typeof firstItem;
  }
  return "string";
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
.model-param-grid-form {
  max-height: 500px;
  overflow-y: auto;
}
</style>
