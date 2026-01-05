<template>
  <default-layout>
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="text-center mb-8">
        <h1 class="text-4xl font-bold text-gray-900 mb-2">
          Welcome to Xenix
        </h1>
        <p class="text-lg text-gray-600">
          Machine Learning Model Training Platform
        </p>
      </div>

      <a-card class="mb-6">
        <div class="flex justify-between items-center mb-4">
          <h2 class="text-2xl font-semibold">Projects</h2>
          <a-button
            type="primary"
            @click="showCreateModal = true"
          >
            <span class="i-mdi-plus mr-1" />
            Create Project
          </a-button>
        </div>

        <a-spin :spinning="isLoading">
          <a-empty
            v-if="projects.length === 0 && !isLoading"
            description="No projects yet. Create your first project to get started!"
          />

          <div v-else class="space-y-4">
            <project-card
              v-for="project in projects"
              :key="project.id"
              :project="project"
              @edit="handleEdit"
              @delete="handleDelete"
              @manage-datasets="handleManageDatasets"
              @add-work-item="handleAddWorkItem"
            />
          </div>
        </a-spin>
      </a-card>

      <!-- Create Project Modal -->
      <project-form-modal
        v-model:open="showCreateModal"
        title="Create New Project"
        @submit="handleCreate"
      />

      <!-- Edit Project Modal -->
      <project-form-modal
        v-model:open="showEditModal"
        title="Edit Project"
        :initial-values="editingProject"
        :show-status="true"
        @submit="handleUpdate"
      />
    </div>
  </default-layout>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { message } from 'ant-design-vue';
import type { Project } from '@xenix/shared';
import DefaultLayout from '../layouts/DefaultLayout.vue';
import ProjectCard from '../components/project/ProjectCard.vue';
import ProjectFormModal from '../components/project/ProjectFormModal.vue';
import { ProjectService } from '../services';

const router = useRouter();

const projects = ref<Project[]>([]);
const isLoading = ref(false);
const showCreateModal = ref(false);
const showEditModal = ref(false);
const editingProject = ref<Partial<Project>>({});

const fetchProjects = async () => {
  isLoading.value = true;
  try {
    const response = await ProjectService.fetchAll();
    if (response.success) {
      projects.value = response.projects;
    }
  } catch (error: any) {
    console.error('Failed to fetch projects:', error);
    message.error('Failed to load projects');
  } finally {
    isLoading.value = false;
  }
};

const handleCreate = async (values: { name: string; description?: string }) => {
  try {
    const response = await ProjectService.create(values);
    if (response.success) {
      message.success('Project created successfully');
      showCreateModal.value = false;
      await fetchProjects();
    }
  } catch (error: any) {
    console.error('Failed to create project:', error);
    message.error('Failed to create project');
  }
};

const handleEdit = (project: Project) => {
  editingProject.value = { ...project };
  showEditModal.value = true;
};

const handleUpdate = async (values: any) => {
  if (!editingProject.value.id) return;
  
  try {
    const response = await ProjectService.update(editingProject.value.id, values);
    if (response.success) {
      message.success('Project updated successfully');
      showEditModal.value = false;
      await fetchProjects();
    }
  } catch (error: any) {
    console.error('Failed to update project:', error);
    message.error('Failed to update project');
  }
};

const handleDelete = async (projectId: number) => {
  try {
    const response = await ProjectService.delete(projectId);
    if (response.success) {
      message.success('Project deleted successfully');
      await fetchProjects();
    }
  } catch (error: any) {
    console.error('Failed to delete project:', error);
    message.error('Failed to delete project');
  }
};

const handleManageDatasets = (projectId: number) => {
  router.push(`/projects/${projectId}/datasets`);
};

const handleAddWorkItem = (projectId: number) => {
  router.push(`/work-items/new?projectId=${projectId}`);
};

onMounted(() => {
  fetchProjects();
});
</script>

<style lang="scss" scoped>
// Styles handled by Tailwind/UnoCSS
</style>
