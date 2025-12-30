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
          :required="schema.required?.includes(propName)"
        >
          <template #extra>
            <div v-if="propSchema.description" class="text-xs text-gray-500">
              {{ propSchema.description }}
            </div>
            <div v-if="propSchema.default !== undefined" class="text-xs text-gray-400">
              {{ t("autoForm.defaultValue") }}:
              <code class="bg-gray-100 px-1 py-0.5 rounded">{{
                JSON.stringify(propSchema.default)
              }}</code>
            </div>
          </template>

          <!-- Array input (type: "array") -->
          <ArrayInput
            v-if="propSchema.type === 'array'"
            v-model="formData[propName as string]"
            :item-type="getArrayItemType(propSchema)"
            :placeholder="t('autoForm.arrayPlaceholder')"
          />

          <!-- Boolean input (type: "boolean") -->
          <a-switch
            v-else-if="propSchema.type === 'boolean'"
            v-model:checked="formData[propName as string]"
          />

          <!-- Number/Integer input (type: "number" or "integer") -->
          <a-input-number
            v-else-if="propSchema.type === 'number' || propSchema.type === 'integer'"
            v-model:value="formData[propName as string]"
            class="w-full"
            :step="propSchema.type === 'integer' ? 1 : 0.01"
            :min="propSchema.minimum"
            :max="propSchema.maximum"
          />

          <!-- String select (type: "string" with enum) -->
          <a-select
            v-else-if="propSchema.type === 'string' && propSchema.enum"
            v-model:value="formData[propName as string]"
            class="w-full"
          >
            <a-select-option
              v-for="option in propSchema.enum"
              :key="option"
              :value="option"
            >
              {{ option }}
            </a-select-option>
          </a-select>

          <!-- String input (type: "string" without enum) -->
          <a-input
            v-else-if="propSchema.type === 'string'"
            v-model:value="formData[propName as string]"
          />

          <!-- Fallback for unsupported types -->
          <a-input
            v-else
            v-model:value="formData[propName as string]"
            :placeholder="`Unsupported type: ${propSchema.type}`"
          />
        </a-form-item>
      </template>
    </div>
  </a-form>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from "vue";
import { useI18n } from "vue-i18n";
import ArrayInput from "./ArrayInput.vue";

interface AutoFormProps {
  modelValue: Record<string, any>;
  schema: any;
}

const props = defineProps<AutoFormProps>();

const emit = defineEmits<{
  "update:modelValue": [value: Record<string, any>];
}>();

const { t } = useI18n();

const formRef = ref();
const formData = ref<Record<string, any>>({});
const isInitializing = ref(false);

const getArrayItemType = (propSchema: any): string => {
  if (propSchema.items && propSchema.items.type) {
    return propSchema.items.type;
  }
  return "string";
};

const formatFieldLabel = (fieldName: string): string => {
  return fieldName
    .replace(/model__/g, "")
    .replace(/_/g, " ")
    .split(" ")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
};

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
        // Use schema defaults
        data[propName] = schema.default;
      } else {
        // Create default value based on type
        if (schema.type === "array") {
          data[propName] = [];
        } else if (schema.type === "boolean") {
          data[propName] = false;
        } else if (schema.type === "number" || schema.type === "integer") {
          data[propName] = 0;
        } else if (schema.type === "string") {
          data[propName] = schema.enum ? schema.enum[0] : "";
        } else {
          data[propName] = null;
        }
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
    initializeFormData();
  },
  { immediate: true, deep: true }
);

// Watch formData and emit updates
watch(
  formData,
  (newData) => {
    if (!isInitializing.value) {
      emit("update:modelValue", { ...newData });
    }
  },
  { deep: true }
);
</script>

<style scoped>
.auto-form {
  max-width: 600px;
}
</style>
