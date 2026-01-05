<template>
  <a-modal
    :open="open"
    :title="title"
    @ok="handleSubmit"
    @cancel="handleCancel"
  >
    <a-form
      :model="formData"
      layout="vertical"
    >
      <a-form-item
        label="Project Name"
        name="name"
        :rules="[{ required: true, message: 'Please enter project name' }]"
      >
        <a-input
          v-model:value="formData.name"
          placeholder="Enter project name"
        />
      </a-form-item>

      <a-form-item
        label="Description"
        name="description"
      >
        <a-textarea
          v-model:value="formData.description"
          placeholder="Enter project description (optional)"
          :rows="3"
        />
      </a-form-item>

      <a-form-item
        v-if="showStatus"
        label="Status"
        name="status"
      >
        <a-select v-model:value="formData.status">
          <a-select-option value="active">Active</a-select-option>
          <a-select-option value="completed">Completed</a-select-option>
          <a-select-option value="archived">Archived</a-select-option>
        </a-select>
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue';

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
  'update:open': [value: boolean];
  submit: [values: any];
}>();

const formData = ref({
  name: '',
  description: '',
  status: 'active',
});

watch(() => props.open, (isOpen) => {
  if (isOpen) {
    if (props.initialValues.id) {
      formData.value = {
        name: props.initialValues.name || '',
        description: props.initialValues.description || '',
        status: props.initialValues.status || 'active',
      };
    } else {
      formData.value = {
        name: '',
        description: '',
        status: 'active',
      };
    }
  }
});

const handleSubmit = () => {
  if (!formData.value.name.trim()) {
    return;
  }
  emit('submit', formData.value);
};

const handleCancel = () => {
  emit('update:open', false);
};
</script>
