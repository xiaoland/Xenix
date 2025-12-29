<template>
  <div class="min-h-screen bg-gray-50 py-8">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <PageHeader />

      <div class="text-center mb-8">
        <h1 class="text-4xl font-bold text-gray-900 mb-2">
          {{ $t("home.title") }}
        </h1>
        <p class="text-lg text-gray-600">
          {{ $t("home.subtitle") }}
        </p>
      </div>

      <!-- Projects Section -->
      <a-card class="mb-6">
        <div class="flex justify-between items-center mb-4">
          <h2 class="text-2xl font-semibold">{{ $t("home.projects") }}</h2>
          <a-button type="primary" @click="showCreateProjectModal = true">
            <template #icon><span class="i-mdi-plus" /></template>
            {{ $t("home.createProject") }}
          </a-button>
        </div>

        <a-spin :spinning="isLoadingProjects">
          <a-empty
            v-if="projects.length === 0"
            :description="$t('home.noProjects')"
          />

          <a-list v-else :data-source="projects" item-layout="horizontal">
            <template #renderItem="{ item }">
              <a-list-item>
                <template #actions>
                  <a-button type="link" @click="viewProjectDetails(item)">
                    {{ $t("projects.viewDetails") }}
                  </a-button>
                  <a-button type="link" @click="editProject(item)">
                    {{ $t("projects.editProject") }}
                  </a-button>
                  <a-popconfirm
                    :title="$t('projects.deleteConfirm')"
                    @confirm="deleteProject(item.projectId)"
                  >
                    <a-button type="link" danger>
                      {{ $t("projects.deleteProject") }}
                    </a-button>
                  </a-popconfirm>
                </template>

                <a-list-item-meta>
                  <template #title>
                    <span class="text-lg font-medium">{{ item.name }}</span>
                    <a-tag class="ml-2" :color="getStatusColor(item.status)">
                      {{ $t(`projects.${item.status}`) }}
                    </a-tag>
                  </template>
                  <template #description>
                    <div class="space-y-1">
                      <div v-if="item.description">{{ item.description }}</div>
                      <div class="text-sm text-gray-500">
                        <span>
                          {{ $t("projects.datasetsCount", { count: item.datasetIds?.length || 0 }) }}
                        </span>
                        <span class="ml-4">
                          {{ $t("projects.workItemsCount", { count: item.workItemIds?.length || 0 }) }}
                        </span>
                      </div>
                      <div class="text-xs text-gray-400">
                        {{ $t("projects.created") }}: {{ formatDate(item.createdAt) }}
                      </div>
                    </div>
                  </template>
                </a-list-item-meta>
              </a-list-item>
            </template>
          </a-list>
        </a-spin>
      </a-card>

      <!-- Work Items Section -->
      <a-card>
        <div class="flex justify-between items-center mb-4">
          <h2 class="text-2xl font-semibold">{{ $t("home.workItems") }}</h2>
          <a-button
            type="primary"
            @click="showCreateWorkItemModal = true"
            :disabled="projects.length === 0"
          >
            <template #icon><span class="i-mdi-plus" /></template>
            {{ $t("workItems.createNew") }}
          </a-button>
        </div>

        <a-spin :spinning="isLoadingWorkItems">
          <a-empty
            v-if="workItems.length === 0"
            :description="$t('home.noWorkItems')"
          />

          <a-list v-else :data-source="workItems" item-layout="horizontal">
            <template #renderItem="{ item }">
              <a-list-item>
                <template #actions>
                  <a-button type="primary" @click="openWorkItem(item.workItemId)">
                    {{ $t("workItems.open") }}
                  </a-button>
                  <a-button type="link" @click="editWorkItem(item)">
                    {{ $t("workItems.editWorkItem") }}
                  </a-button>
                  <a-popconfirm
                    :title="$t('workItems.deleteConfirm')"
                    @confirm="deleteWorkItem(item.workItemId)"
                  >
                    <a-button type="link" danger>
                      {{ $t("workItems.deleteWorkItem") }}
                    </a-button>
                  </a-popconfirm>
                </template>

                <a-list-item-meta>
                  <template #title>
                    <span class="text-lg font-medium">{{ item.name }}</span>
                    <a-tag class="ml-2" :color="getStatusColor(item.status)">
                      {{ $t(`workItems.${item.status}`) }}
                    </a-tag>
                  </template>
                  <template #description>
                    <div class="space-y-1">
                      <div v-if="item.description">{{ item.description }}</div>
                      <div class="text-sm text-gray-500">
                        <span>{{ getProjectName(item.projectId) }}</span>
                        <span class="ml-4">
                          {{ $t("workItems.tasksCount", { count: item.taskIds?.length || 0 }) }}
                        </span>
                      </div>
                      <div class="text-xs text-gray-400">
                        {{ $t("workItems.created") }}: {{ formatDate(item.createdAt) }}
                      </div>
                    </div>
                  </template>
                </a-list-item-meta>
              </a-list-item>
            </template>
          </a-list>
        </a-spin>
      </a-card>

      <!-- Create Project Modal -->
      <a-modal
        v-model:open="showCreateProjectModal"
        :title="$t('projects.createNew')"
        @ok="handleCreateProject"
        @cancel="resetProjectForm"
      >
        <a-form layout="vertical">
          <a-form-item :label="$t('projects.name')" required>
            <a-input
              v-model:value="newProject.name"
              :placeholder="$t('projects.namePlaceholder')"
            />
          </a-form-item>
          <a-form-item :label="$t('projects.description')">
            <a-textarea
              v-model:value="newProject.description"
              :placeholder="$t('projects.descriptionPlaceholder')"
              :rows="3"
            />
          </a-form-item>
        </a-form>
      </a-modal>

      <!-- Edit Project Modal -->
      <a-modal
        v-model:open="showEditProjectModal"
        :title="$t('projects.editProject')"
        @ok="handleUpdateProject"
        @cancel="resetProjectForm"
      >
        <a-form layout="vertical">
          <a-form-item :label="$t('projects.name')" required>
            <a-input
              v-model:value="editingProject.name"
              :placeholder="$t('projects.namePlaceholder')"
            />
          </a-form-item>
          <a-form-item :label="$t('projects.description')">
            <a-textarea
              v-model:value="editingProject.description"
              :placeholder="$t('projects.descriptionPlaceholder')"
              :rows="3"
            />
          </a-form-item>
          <a-form-item :label="$t('projects.status')">
            <a-select v-model:value="editingProject.status">
              <a-select-option value="active">{{ $t("projects.active") }}</a-select-option>
              <a-select-option value="completed">{{ $t("projects.completed") }}</a-select-option>
              <a-select-option value="archived">{{ $t("projects.archived") }}</a-select-option>
            </a-select>
          </a-form-item>
        </a-form>
      </a-modal>

      <!-- Create Work Item Modal -->
      <a-modal
        v-model:open="showCreateWorkItemModal"
        :title="$t('workItems.createNew')"
        @ok="handleCreateWorkItem"
        @cancel="resetWorkItemForm"
      >
        <a-form layout="vertical">
          <a-form-item :label="$t('workItems.selectProject')" required>
            <a-select
              v-model:value="newWorkItem.projectId"
              :placeholder="$t('workItems.selectProjectPlaceholder')"
            >
              <a-select-option
                v-for="project in projects"
                :key="project.projectId"
                :value="project.projectId"
              >
                {{ project.name }}
              </a-select-option>
            </a-select>
          </a-form-item>
          <a-form-item :label="$t('workItems.name')" required>
            <a-input
              v-model:value="newWorkItem.name"
              :placeholder="$t('workItems.namePlaceholder')"
            />
          </a-form-item>
          <a-form-item :label="$t('workItems.description')">
            <a-textarea
              v-model:value="newWorkItem.description"
              :placeholder="$t('workItems.descriptionPlaceholder')"
              :rows="3"
            />
          </a-form-item>
        </a-form>
      </a-modal>

      <!-- Edit Work Item Modal -->
      <a-modal
        v-model:open="showEditWorkItemModal"
        :title="$t('workItems.editWorkItem')"
        @ok="handleUpdateWorkItem"
        @cancel="resetWorkItemForm"
      >
        <a-form layout="vertical">
          <a-form-item :label="$t('workItems.name')" required>
            <a-input
              v-model:value="editingWorkItem.name"
              :placeholder="$t('workItems.namePlaceholder')"
            />
          </a-form-item>
          <a-form-item :label="$t('workItems.description')">
            <a-textarea
              v-model:value="editingWorkItem.description"
              :placeholder="$t('workItems.descriptionPlaceholder')"
              :rows="3"
            />
          </a-form-item>
          <a-form-item :label="$t('workItems.status')">
            <a-select v-model:value="editingWorkItem.status">
              <a-select-option value="active">{{ $t("workItems.active") }}</a-select-option>
              <a-select-option value="completed">{{ $t("workItems.completed") }}</a-select-option>
              <a-select-option value="archived">{{ $t("workItems.archived") }}</a-select-option>
            </a-select>
          </a-form-item>
        </a-form>
      </a-modal>

      <!-- Project Details Modal -->
      <a-modal
        v-model:open="showProjectDetailsModal"
        :title="selectedProject?.name"
        :footer="null"
        width="800px"
      >
        <div v-if="selectedProject" class="space-y-4">
          <a-descriptions bordered :column="2">
            <a-descriptions-item :label="$t('projects.projectId')">
              {{ selectedProject.projectId }}
            </a-descriptions-item>
            <a-descriptions-item :label="$t('projects.status')">
              {{ $t(`projects.${selectedProject.status}`) }}
            </a-descriptions-item>
            <a-descriptions-item :label="$t('projects.created')" :span="2">
              {{ formatDate(selectedProject.createdAt) }}
            </a-descriptions-item>
            <a-descriptions-item
              v-if="selectedProject.description"
              :label="$t('projects.description')"
              :span="2"
            >
              {{ selectedProject.description }}
            </a-descriptions-item>
          </a-descriptions>

          <div>
            <h3 class="font-semibold mb-2">
              {{ $t("projects.datasetsCount", { count: selectedProject.datasetIds?.length || 0 }) }}
            </h3>
            <div v-if="selectedProject.datasetIds?.length > 0" class="flex flex-wrap gap-2">
              <a-tag v-for="datasetId in selectedProject.datasetIds" :key="datasetId" color="blue">
                {{ datasetId }}
              </a-tag>
            </div>
            <div v-else class="text-gray-400">{{ $t("home.noProjects") }}</div>
          </div>

          <div>
            <h3 class="font-semibold mb-2">
              {{ $t("projects.workItemsCount", { count: selectedProject.workItemIds?.length || 0 }) }}
            </h3>
            <div v-if="selectedProject.workItemIds?.length > 0" class="flex flex-wrap gap-2">
              <a-tag v-for="workItemId in selectedProject.workItemIds" :key="workItemId" color="green">
                {{ getWorkItemName(workItemId) }}
              </a-tag>
            </div>
            <div v-else class="text-gray-400">{{ $t("home.noWorkItems") }}</div>
          </div>
        </div>
      </a-modal>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { message } from "ant-design-vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import type { Project, WorkItem } from "../types";

const { t } = useI18n();
const router = useRouter();

const projects = ref<Project[]>([]);
const workItems = ref<WorkItem[]>([]);
const isLoadingProjects = ref(false);
const isLoadingWorkItems = ref(false);

const showCreateProjectModal = ref(false);
const showEditProjectModal = ref(false);
const showCreateWorkItemModal = ref(false);
const showEditWorkItemModal = ref(false);
const showProjectDetailsModal = ref(false);

const newProject = ref({
  name: "",
  description: "",
});

const editingProject = ref<Partial<Project>>({});
const selectedProject = ref<Project | null>(null);

const newWorkItem = ref({
  projectId: "",
  name: "",
  description: "",
});

const editingWorkItem = ref<Partial<WorkItem>>({});

const fetchProjects = async () => {
  isLoadingProjects.value = true;
  try {
    const response = await $fetch("/api/projects");
    if (response.success) {
      projects.value = response.projects;
    }
  } catch (error) {
    console.error("Failed to fetch projects:", error);
    message.error(t("projects.fetchError"));
  } finally {
    isLoadingProjects.value = false;
  }
};

const fetchWorkItems = async () => {
  isLoadingWorkItems.value = true;
  try {
    const response = await $fetch("/api/work-items");
    if (response.success) {
      workItems.value = response.workItems;
    }
  } catch (error) {
    console.error("Failed to fetch work items:", error);
    message.error(t("workItems.fetchError"));
  } finally {
    isLoadingWorkItems.value = false;
  }
};

const handleCreateProject = async () => {
  if (!newProject.value.name.trim()) {
    message.error(t("projects.createError"));
    return;
  }

  try {
    const response = await $fetch("/api/projects", {
      method: "POST",
      body: newProject.value,
    });

    if (response.success) {
      message.success(t("projects.createSuccess"));
      showCreateProjectModal.value = false;
      resetProjectForm();
      await fetchProjects();
    }
  } catch (error) {
    console.error("Failed to create project:", error);
    message.error(t("projects.createError"));
  }
};

const handleCreateWorkItem = async () => {
  if (!newWorkItem.value.name.trim() || !newWorkItem.value.projectId) {
    message.error(t("workItems.createError"));
    return;
  }

  try {
    const response = await $fetch("/api/work-items", {
      method: "POST",
      body: newWorkItem.value,
    });

    if (response.success) {
      message.success(t("workItems.createSuccess"));
      showCreateWorkItemModal.value = false;
      resetWorkItemForm();
      await fetchWorkItems();
      await fetchProjects(); // Refresh to update work item counts
    }
  } catch (error) {
    console.error("Failed to create work item:", error);
    message.error(t("workItems.createError"));
  }
};

const editProject = (project: Project) => {
  editingProject.value = { ...project };
  showEditProjectModal.value = true;
};

const handleUpdateProject = async () => {
  if (!editingProject.value.projectId) return;

  try {
    const response = await $fetch(`/api/projects/${editingProject.value.projectId}`, {
      method: "PUT",
      body: {
        name: editingProject.value.name,
        description: editingProject.value.description,
        status: editingProject.value.status,
      },
    });

    if (response.success) {
      message.success(t("projects.updateSuccess"));
      showEditProjectModal.value = false;
      await fetchProjects();
    }
  } catch (error) {
    console.error("Failed to update project:", error);
    message.error(t("projects.updateError"));
  }
};

const deleteProject = async (projectId: string) => {
  try {
    const response = await $fetch(`/api/projects/${projectId}`, {
      method: "DELETE",
    });

    if (response.success) {
      message.success(t("projects.deleteSuccess"));
      await fetchProjects();
      await fetchWorkItems(); // Refresh work items as they might be affected
    }
  } catch (error) {
    console.error("Failed to delete project:", error);
    message.error(t("projects.deleteError"));
  }
};

const editWorkItem = (workItem: WorkItem) => {
  editingWorkItem.value = { ...workItem };
  showEditWorkItemModal.value = true;
};

const handleUpdateWorkItem = async () => {
  if (!editingWorkItem.value.workItemId) return;

  try {
    const response = await $fetch(`/api/work-items/${editingWorkItem.value.workItemId}`, {
      method: "PUT",
      body: {
        name: editingWorkItem.value.name,
        description: editingWorkItem.value.description,
        status: editingWorkItem.value.status,
      },
    });

    if (response.success) {
      message.success(t("workItems.updateSuccess"));
      showEditWorkItemModal.value = false;
      await fetchWorkItems();
    }
  } catch (error) {
    console.error("Failed to update work item:", error);
    message.error(t("workItems.updateError"));
  }
};

const deleteWorkItem = async (workItemId: string) => {
  try {
    const response = await $fetch(`/api/work-items/${workItemId}`, {
      method: "DELETE",
    });

    if (response.success) {
      message.success(t("workItems.deleteSuccess"));
      await fetchWorkItems();
      await fetchProjects(); // Refresh to update work item counts
    }
  } catch (error) {
    console.error("Failed to delete work item:", error);
    message.error(t("workItems.deleteError"));
  }
};

const openWorkItem = (workItemId: string) => {
  router.push(`/work-items/${workItemId}`);
};

const viewProjectDetails = (project: Project) => {
  selectedProject.value = project;
  showProjectDetailsModal.value = true;
};

const resetProjectForm = () => {
  newProject.value = {
    name: "",
    description: "",
  };
  editingProject.value = {};
};

const resetWorkItemForm = () => {
  newWorkItem.value = {
    projectId: "",
    name: "",
    description: "",
  };
  editingWorkItem.value = {};
};

const getStatusColor = (status: string) => {
  switch (status) {
    case "active":
      return "green";
    case "completed":
      return "blue";
    case "archived":
      return "gray";
    default:
      return "default";
  }
};

const getProjectName = (projectId?: string) => {
  if (!projectId) return "";
  const project = projects.value.find((p) => p.projectId === projectId);
  return project ? project.name : projectId;
};

const getWorkItemName = (workItemId: string) => {
  const workItem = workItems.value.find((w) => w.workItemId === workItemId);
  return workItem ? workItem.name : workItemId;
};

const formatDate = (dateString: string): string => {
  if (!dateString) return "";
  const date = new Date(dateString);
  return date.toLocaleString();
};

onMounted(() => {
  fetchProjects();
  fetchWorkItems();
});
</script>
