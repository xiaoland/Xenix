<template>
  <default-layout>
    <div class="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div class="mb-6">
        <a-breadcrumb>
          <a-breadcrumb-item>
            <router-link to="/">{{ $t("navigation.home") }}</router-link>
          </a-breadcrumb-item>
          <a-breadcrumb-item>{{ $t("workItems.createNew") }}</a-breadcrumb-item>
        </a-breadcrumb>
      </div>

      <a-card :title="$t('workItems.createNew')">
        <a-form
          :model="formState"
          :rules="rules"
          layout="vertical"
          @finish="handleSubmit"
        >
          <a-form-item
            v-if="!projectId"
            :label="$t('workItems.selectProject')"
            name="projectId"
          >
            <a-select
              v-model:value="formState.projectId"
              :placeholder="$t('workItems.selectProjectPlaceholder')"
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
            :message="
              $t('workItems.creatingFor', { project: selectedProject.name })
            "
            type="info"
            show-icon
            class="mb-4"
          />

          <a-form-item :label="$t('workItems.name')" name="name">
            <a-input
              v-model:value="formState.name"
              :placeholder="$t('workItems.namePlaceholder')"
            />
          </a-form-item>

          <a-form-item :label="$t('workItems.description')" name="description">
            <a-textarea
              v-model:value="formState.description"
              :placeholder="$t('workItems.descriptionPlaceholder')"
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
                {{ $t("workItems.createButton") }}
              </a-button>
              <a-button @click="handleCancel">
                {{ $t("common.cancel") }}
              </a-button>
            </div>
          </a-form-item>
        </a-form>
      </a-card>
    </div>
  </default-layout>
</template>

<script setup lang="ts">
import { message } from "ant-design-vue";

import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";

import type { Project } from "@xenix/shared";

import { useCreateWorkItem, useProjects } from "../../composables";
import DefaultLayout from "../../layouts/DefaultLayout.vue";

const router = useRouter();
const route = useRoute();
const { t } = useI18n();

const projectId = computed(() => {
  const id = route.query.projectId;
  return id ? Number(id) : null;
});

// Use composables for data fetching
const { data: projectsData, isLoading: isLoadingProjects } = useProjects();
const { mutate: createWorkItem, isPending: isSubmitting } = useCreateWorkItem();

const projects = computed(() =>
  Array.isArray(projectsData.value) ? projectsData.value : []
);

const formState = ref({
  projectId: projectId.value || undefined,
  name: "",
  description: "",
});

const selectedProject = computed(() => {
  if (!projectId.value) return null;
  return (projects.value as Project[]).find(
    (p: Project) => p.id === projectId.value
  );
});

const rules = {
  projectId: [
    {
      required: true,
      message: t("workItems.selectProjectRequired"),
      type: "number" as const,
    },
  ],
  name: [
    {
      required: true,
      message: t("workItems.nameRequired"),
      trigger: "blur",
    },
    {
      min: 2,
      message: t("workItems.nameMinLength"),
      trigger: "blur",
    },
  ],
};

const handleSubmit = () => {
  if (!formState.value.projectId) {
    message.error(t("workItems.selectProjectRequired"));
    return;
  }

  createWorkItem(
    {
      projectId: formState.value.projectId,
      name: formState.value.name,
      description: formState.value.description || undefined,
    },
    {
      onSuccess: (workItem) => {
        message.success(t("workItems.createSuccess"));
        // Navigate to the work item detail page
        router.push(`/work-items/${workItem.id}`);
      },
      onError: (error: any) => {
        console.error("Failed to create work item:", error);
        message.error(t("workItems.createError"));
      },
    }
  );
};

const handleCancel = () => {
  router.push("/");
};
</script>

<style lang="scss" scoped>
// Styles handled by Tailwind/UnoCSS and Ant Design Vue
</style>
