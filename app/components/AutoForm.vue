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
                JSON.stringify(getDefaultValue(propSchema, mode))
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
              :placeholder="getDefaultValue(propSchema, mode).toString()"
              class="w-full"
            />
            <!-- String input -->
            <a-input
              v-else
              v-model:value="formData[propName as string]"
              :placeholder="getDefaultValue(propSchema, mode).toString()"
            />
          </template>
        </a-form-item>
      </template>
    </div>
  </a-form>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from "vue";
import {
  formatFieldLabel,
  getArrayItemType,
  getItemType,
  getDefaultValue,
  createDefaultValue,
} from "../utils/schemaHelpers";

const { t } = useI18n();

interface AutoFormProps {
  modelValue: Record<string, any>;
  schema: any;
}

const props = defineProps<AutoFormProps>();

const emit = defineEmits<{
  "update:modelValue": [value: Record<string, any>];
}>();

const formRef = ref();
const formData = ref<Record<string, any>>({});
const isInitializing = ref(false);

// Determine mode based on schema structure
// If the first property has items (array type), it's paramGrid mode
const mode = computed(() => {
  if (props.schema && props.schema.properties) {
    const firstProp = Object.values(props.schema.properties)[0] as any;
    if (firstProp && firstProp.items) {
      return "paramGrid";
    }
  }
  return "parameters";
});

const initializeFormData = () => {
  isInitializing.value = true;
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
        if (mode.value === "paramGrid") {
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
        const itemType = getItemType(schema);
        data[propName] = createDefaultValue(itemType, mode.value);
      }
    }
  }

  formData.value = data;
  // Use nextTick to ensure the update is complete before allowing emissions
  nextTick(() => {
    isInitializing.value = false;
  });
};

// Initialize form data when schema or initial values change
watch(
  () => [props.modelValue, props.schema],
  () => {
    if (props.schema) {
      initializeFormData();
    }
  },
  { immediate: true, deep: true }
);

// Emit changes to parent (only when not initializing)
watch(
  formData,
  (newValue) => {
    if (!isInitializing.value) {
      emit("update:modelValue", newValue);
    }
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
