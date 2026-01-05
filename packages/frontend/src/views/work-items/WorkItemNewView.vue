<template>
  <default-layout>
    <div class="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div class="mb-6">
        <a-breadcrumb>
          <a-breadcrumb-item>
            <router-link to="/">Home</router-link>
          </a-breadcrumb-item>
          <a-breadcrumb-item>New Work Item</a-breadcrumb-item>
        </a-breadcrumb>
      </div>

      <a-card title="Create New Work Item">
        <a-form
          :model="formState"
          :rules="rules"
          layout="vertical"
          @finish="handleSubmit"
        >
          <a-form-item
            label="Project"
            name="projectId"
            v-if="!projectId"
          >
            <a-select
              v-model:value="formState.projectId"
              placeholder="Select a project"
              :loading="isLoadingProjects"
            >
              <a-select-option
                v-for="project in projects"
                :key="project.id"
                :value="project.id"
              >
                {{ project.name }}
              </a-select-option>
            </a-select>
          </a-form-item>

          <a-alert
            v-if="projectId && selectedProject"
            :message="`Creating work item for project: ${selectedProject.name}`"
            type="info"
            show-icon
            class="mb-4"
          />

          <a-form-item
            label="Work Item Name"
            name="name"
          >
            <a-input
              v-model:value="formState.name"
              placeholder="Enter work item name"
            />
          </a-form-item>

          <a-form-item
            label="Description"
            name="description"
          >
            <a-textarea
              v-model:value="formState.description"
              placeholder="Enter work item description (optional)"
              :rows="4"
            />
          </a-form-item>

          <a-form-item>
            <div class="flex gap-2">
              <a-button
                type="primary"
                html-type="submit"
                :loading="isSubmitting"
              >
                Create Work Item
              </a-button>
              <a-button @click="handleCancel">
                Cancel
              </a-button>
            </div>
          </a-form-item>
        </a-form>
      </a-card>
    </div>
  </default-layout>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { message } from 'ant-design-vue';
import type { Project } from '@xenix/shared';
import DefaultLayout from '../../layouts/DefaultLayout.vue';
import { WorkItemService, ProjectService } from '../../services';

const router = useRouter();
const route = useRoute();

const projectId = computed(() => {
  const id = route.query.projectId;
  return id ? Number(id) : null;
});

const projects = ref<Project[]>([]);
const isLoadingProjects = ref(false);
const isSubmitting = ref(false);

const formState = ref({
  projectId: projectId.value || undefined,
  name: '',
  description: '',
});

const selectedProject = computed(() => {
  if (!projectId.value) return null;
  return projects.value.find(p => p.id === projectId.value);
});

const rules = {
  projectId: [
    { required: true, message: 'Please select a project', type: 'number' },
  ],
  name: [
    { required: true, message: 'Please enter work item name', trigger: 'blur' },
    { min: 2, message: 'Name must be at least 2 characters', trigger: 'blur' },
  ],
};

const fetchProjects = async () => {
  isLoadingProjects.value = true;
  try {
    const response = await ProjectService.fetchAll();
    if (response.success) {
      projects.value = response.projects;
    }
  } catch (error: any) {
    console.error('Failed to fetch projects:', error);
    message.error('Failed to load projects');
  } finally {
    isLoadingProjects.value = false;
  }
};

const handleSubmit = async () => {
  if (!formState.value.projectId) {
    message.error('Please select a project');
    return;
  }

  isSubmitting.value = true;
  try {
    const response = await WorkItemService.create({
      projectId: formState.value.projectId,
      name: formState.value.name,
      description: formState.value.description || undefined,
    });

    if (response.success) {
      message.success('Work item created successfully');
      // Navigate to the work item detail page
      router.push(`/work-items/${response.workItem.id}`);
    }
  } catch (error: any) {
    console.error('Failed to create work item:', error);
    message.error('Failed to create work item');
  } finally {
    isSubmitting.value = false;
  }
};

const handleCancel = () => {
  router.push('/');
};

onMounted(() => {
  fetchProjects();
});
</script>

<style lang="scss" scoped>
// Styles handled by Tailwind/UnoCSS and Ant Design Vue
</style>
