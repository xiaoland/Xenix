<template>
  <a-modal
    :open="open"
    :title="title"
    @ok="handleSubmit"
    @cancel="handleCancel"
  >
    <a-form :model="formData" layout="vertical">
      <a-form-item
        :label="$t('project.form.name')"
        name="name"
        :rules="[
          {
            required: true,
            message: $t('project.form.nameRequired'),
          },
        ]"
      >
        <a-input
          v-model:value="formData.name"
          :placeholder="$t('project.form.namePlaceholder')"
        />
      </a-form-item>

      <a-form-item :label="$t('project.form.description')" name="description">
        <a-textarea
          v-model:value="formData.description"
          :placeholder="$t('project.form.descriptionPlaceholder')"
          :rows="3"
        />
      </a-form-item>

      <a-form-item
        v-if="showStatus"
        :label="$t('project.form.status')"
        name="status"
      >
        <a-select v-model:value="formData.status">
          <a-select-option value="active">{{
            $t("project.form.active")
          }}</a-select-option>
          <a-select-option value="completed">{{
            $t("project.form.completed")
          }}</a-select-option>
          <a-select-option value="archived">{{
            $t("project.form.archived")
          }}</a-select-option>
        </a-select>
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, watch } from "vue";

interface Props {
  open: boolean;
  title: string;
  initialValues?: any;
  showStatus?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  initialValues: () => ({}),
  showStatus: false,
});

const emit = defineEmits<{
  "update:open": [value: boolean];
  submit: [values: any];
}>();

const formData = ref({
  name: "",
  description: "",
  status: "active",
});

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      if (props.initialValues.id) {
        formData.value = {
          name: props.initialValues.name || "",
          description: props.initialValues.description || "",
          status: props.initialValues.status || "active",
        };
      } else {
        formData.value = {
          name: "",
          description: "",
          status: "active",
        };
      }
    }
  }
);

const handleSubmit = () => {
  if (!formData.value.name.trim()) {
    return;
  }
  emit("submit", formData.value);
};

const handleCancel = () => {
  emit("update:open", false);
};
</script>
