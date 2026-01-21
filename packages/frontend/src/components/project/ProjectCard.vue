<template>
  <div
    class="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow"
  >
    <div class="flex items-start justify-between mb-2">
      <div class="flex-1">
        <div class="flex items-center gap-2 mb-2">
          <span class="i-mdi-folder text-blue-500 text-xl"></span>
          <span class="text-lg font-semibold">{{ project.name }}</span>
          <a-tag :color="statusColor">
            {{ project.status || "active" }}
          </a-tag>
        </div>
        <p v-if="project.description" class="text-sm text-gray-600 ml-7 mb-2">
          {{ project.description }}
        </p>
        <div class="text-xs text-gray-400 ml-7">
          <span v-if="(project as any).datasets">
            {{ (project as any).datasets.length }}
            {{ $t("projects.datasets") }}
          </span>
          <span v-if="(project as any).workItems">
            · {{ (project as any).workItems.length }}
            {{ $t("projects.workItems") }}
          </span>
          <span>
            · {{ $t("projects.created") }}
            {{ formatDate(project.createdAt) }}
          </span>
        </div>
      </div>

      <div class="flex gap-2">
        <a-button
          size="small"
          class="inline-flex items-center"
          @click="$emit('manage-datasets', project.id)"
        >
          <span class="i-mdi-database mr-1" />
          {{ $t("projects.manageDatasets") }}
        </a-button>
        <a-button
          size="small"
          class="inline-flex items-center"
          @click="$emit('edit', project)"
        >
          <span class="i-mdi-pencil mr-1" />
          {{ $t("projects.edit") }}
        </a-button>
        <a-popconfirm
          :title="$t('projects.deleteConfirm')"
          @confirm="$emit('delete', project.id)"
        >
          <a-button size="small" danger class="inline-flex items-center">
            <span class="i-mdi-delete mr-1" />
            {{ $t("projects.delete") }}
          </a-button>
        </a-popconfirm>
      </div>
    </div>

    <!-- Work Items List -->
    <div
      v-if="(project as any).workItems && (project as any).workItems.length > 0"
      class="ml-7 mt-3 space-y-2"
    >
      <work-item-row
        v-for="workItem in (project as any).workItems"
        :key="workItem.id"
        :work-item="workItem"
      />
    </div>

    <!-- Add Work Item Button -->
    <div class="ml-7 mt-2">
      <a-button
        size="small"
        type="dashed"
        class="inline-flex items-center"
        @click="$emit('add-work-item', project.id)"
      >
        <span class="i-mdi-plus mr-1" />
        {{ $t("projects.addWorkItem") }}
      </a-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";

import type { Project } from "@xenix/shared";

import WorkItemRow from "./WorkItemRow.vue";

interface Props {
  project: Project;
}

const props = defineProps<Props>();

defineEmits<{
  edit: [project: Project];
  delete: [projectId: number];
  "manage-datasets": [projectId: number];
  "add-work-item": [projectId: number];
}>();

const statusColor = computed(() => {
  switch (props.project.status) {
    case "active":
      return "green";
    case "completed":
      return "blue";
    case "archived":
      return "gray";
    default:
      return "default";
  }
});

const formatDate = (dateString?: string) => {
  if (!dateString) return "";
  const date = new Date(dateString);
  return date.toLocaleDateString();
};
</script>
