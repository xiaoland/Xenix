<template>
  <div class="model-param-grid-form">
    <div v-if="schema === undefined" class="text-center py-4">
      <a-spin />
      <p class="mt-2">{{ t("autoForm.loading") }}</p>
    </div>
    <div v-if="schema === null" class="text-center py-4">
      <p class="mt-2 text-red-500">{{ t("modelParamGridForm.noSchema") }}</p>
    </div>
    <AutoForm v-else ref="formRef" v-model="formData" :schema="schema" />
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import { ModelService } from "~/services";
import AutoForm from "~/components/common/AutoForm.vue";

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
const modelMetadata = ref<any>();

// Computed schema from model metadata
const schema = computed(() => {
  return modelMetadata.value?.paramGridSchema;
});

// Fetch model metadata
const fetchModelMetadata = async () => {
  try {
    const response = await ModelService.fetchModel(props.model);
    modelMetadata.value = response.model;
  } catch (error) {
    console.error(`Failed to fetch metadata for ${props.model}:`, error);
  }
};

// Initialize form data from modelValue
watch(
  () => props.modelValue,
  (newVal) => {
    if (newVal) {
      formData.value = { ...newVal };
    }
  },
  { immediate: true }
);

// Watch for changes in formData and emit
watch(
  formData,
  (newVal) => {
    emit("update:modelValue", newVal);
  },
  { deep: true }
);

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
