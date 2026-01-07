<template>
  <default-layout>
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="text-center mb-8">
        <h1 class="text-4xl font-bold text-gray-900 mb-2">
          {{ $t('home.title') }}
        </h1>
        <p class="text-lg text-gray-600">
          {{ $t('home.subtitle') }}
        </p>
      </div>

      <a-card class="mb-6">
        <div class="flex justify-between items-center mb-4">
          <h2 class="text-2xl font-semibold">{{ $t('home.projects') }}</h2>
          <a-button
            type="primary"
            class="inline-flex items-center"
            @click="showCreateModal = true"
          >
            <span class="i-mdi-plus mr-1" />
            {{ $t('home.createProject') }}
          </a-button>
        </div>

        <a-spin :spinning="isLoading">
          <a-empty
            v-if="projects.length === 0 && !isLoading"
            :description="$t('home.noProjects')"
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
        :title="$t('projects.createNew')"
        @submit="handleCreate"
      />

      <!-- Edit Project Modal -->
      <project-form-modal
        v-model:open="showEditModal"
        :title="$t('projects.editProject')"
        :initial-values="editingProject"
        :show-status="true"
        @submit="handleUpdate"
      />
    </div>
  </default-layout>
</template>

<script setup lang="ts">
import { message } from 'ant-design-vue';

import { computed, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRouter } from 'vue-router';

import type { Project } from '@xenix/shared';

import ProjectCard from '../components/project/ProjectCard.vue';
import ProjectFormModal from '../components/project/ProjectFormModal.vue';
import {
  useCreateProject,
  useDeleteProject,
  useProjects,
  useUpdateProject,
} from '../composables';
import DefaultLayout from '../layouts/DefaultLayout.vue';

const router = useRouter();
const { t } = useI18n();

// Use composables for data fetching
const { data: projectsData, isLoading, error } = useProjects();
const { mutate: createProject, isPending: isCreating } = useCreateProject();
const { mutate: updateProject, isPending: isUpdating } = useUpdateProject();
const { mutate: deleteProject, isPending: isDeleting } = useDeleteProject();

// Computed property to safely access projects array
const projects = computed(() => (projectsData.value as any[]) || []);

const showCreateModal = ref(false);
const showEditModal = ref(false);
const editingProject = ref<Partial<Project>>({});

const handleCreate = (values: { name: string; description?: string }) => {
  createProject(values, {
    onSuccess: () => {
      message.success(t('projects.createSuccess'));
      showCreateModal.value = false;
    },
    onError: (error: any) => {
      console.error('Failed to create project:', error);
      message.error(t('projects.createError'));
    },
  });
};

const handleEdit = (project: Project) => {
  editingProject.value = { ...project };
  showEditModal.value = true;
};

const handleUpdate = (values: any) => {
  if (!editingProject.value.id) return;

  updateProject(
    { id: editingProject.value.id, updates: values },
    {
      onSuccess: () => {
        message.success(t('projects.updateSuccess'));
        showEditModal.value = false;
      },
      onError: (error: any) => {
        console.error('Failed to update project:', error);
        message.error(t('projects.updateError'));
      },
    }
  );
};

const handleDelete = (projectId: number) => {
  deleteProject(projectId, {
    onSuccess: () => {
      message.success(t('projects.deleteSuccess'));
    },
    onError: (error: any) => {
      console.error('Failed to delete project:', error);
      message.error(t('projects.deleteError'));
    },
  });
};

const handleManageDatasets = (projectId: number) => {
  router.push(`/projects/${projectId}/datasets`);
};

const handleAddWorkItem = (projectId: number) => {
  router.push(`/work-items/new?projectId=${projectId}`);
};
</script>

<style lang="scss" scoped>
// Styles handled by Tailwind/UnoCSS
</style>
