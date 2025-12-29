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

      <!-- Projects with Nested Work Items (Tree Structure) -->
      <a-card class="mb-6">
        <div class="flex justify-between items-center mb-4">
          <h2 class="text-2xl font-semibold">{{ $t("home.projects") }}</h2>
          <a-button type="primary" class="inline-flex items-center" @click="showCreateProjectModal = true">
            <span class="i-mdi-plus mr-1" />
            {{ $t("home.createProject") }}
          </a-button>
        </div>

        <a-spin :spinning="isLoadingProjects">
          <a-empty
            v-if="projects.length === 0"
            :description="$t('home.noProjects')"
          />

          <!-- Tree structure showing projects and nested work items -->
          <div v-else class="space-y-4">
            <div
              v-for="project in projects"
              :key="project.id"
              class="border border-gray-200 rounded-lg p-4"
            >
              <!-- Project Header -->
              <div class="flex items-start justify-between mb-2">
                <div class="flex-1">
                  <div class="flex items-center gap-2">
                    <span class="i-mdi-folder text-blue-500 text-xl"></span>
                    <span class="text-lg font-semibold">{{ project.name }}</span>
                    <a-tag :color="getStatusColor(project.status)">
                      {{ $t(`projects.${project.status}`) }}
                    </a-tag>
                  </div>
                  <p v-if="project.description" class="text-sm text-gray-600 mt-1 ml-7">
                    {{ project.description }}
                  </p>
                  <div class="text-xs text-gray-400 mt-1 ml-7">
                    {{ $t("projects.datasetsCount", { count: project.datasets?.length || 0 }) }} · 
                    {{ $t("projects.workItemsCount", { count: project.workItems?.length || 0 }) }}
                  </div>
                </div>
                
                <!-- Project Actions -->
                <div class="flex gap-2">
                  <a-button size="small" class="inline-flex items-center" @click="manageProjectDatasets(project.id)">
                    <span class="i-mdi-database mr-1" />
                    Manage Datasets
                  </a-button>
                  <a-button size="small" class="inline-flex items-center" @click="viewEditProjectDetails(project)">
                    <span class="i-mdi-information mr-1" />
                    View Details
                  </a-button>
                  <a-popconfirm
                    :title="$t('projects.deleteConfirm')"
                    @confirm="deleteProject(project.id)"
                  >
                    <a-button size="small" danger class="inline-flex items-center">
                      <span class="i-mdi-delete mr-1" />
                    </a-button>
                  </a-popconfirm>
                </div>
              </div>

              <!-- Nested Work Items -->
              <div v-if="project.workItems && project.workItems.length > 0" class="ml-7 mt-3 space-y-2">
                <div
                  v-for="workItem in project.workItems"
                  :key="workItem.id"
                  class="flex items-center justify-between p-2 bg-gray-50 rounded hover:bg-gray-100 cursor-pointer"
                  @click="openWorkItem(workItem.id)"
                >
                  <div class="flex items-center gap-2 flex-1">
                    <span class="i-mdi-file-document-outline text-green-500"></span>
                    <span class="font-medium">{{ workItem.name }}</span>
                    <a-tag size="small" :color="getStatusColor(workItem.status)">
                      {{ $t(`workItems.${workItem.status}`) }}
                    </a-tag>
                  </div>
                  <div class="flex gap-1" @click.stop>
                    <a-button size="small" type="text" class="inline-flex items-center" @click="editWorkItem(workItem)">
                      <span class="i-mdi-pencil mr-1" />
                    </a-button>
                    <a-popconfirm
                      :title="$t('workItems.deleteConfirm')"
                      @confirm="deleteWorkItem(workItem.id)"
                    >
                      <a-button size="small" type="text" danger class="inline-flex items-center">
                        <span class="i-mdi-delete mr-1" />
                      </a-button>
                    </a-popconfirm>
                  </div>
                </div>
              </div>

              <!-- Add Work Item Button -->
              <div class="ml-7 mt-2">
                <a-button size="small" type="dashed" class="inline-flex items-center" @click="showCreateWorkItemModal = true; newWorkItem.projectId = project.id">
                  <span class="i-mdi-plus mr-1" />
                  Add Work Item
                </a-button>
              </div>
            </div>
          </div>
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

      <!-- View/Edit Project Details Modal -->
      <a-modal
        v-model:open="showProjectDetailsModal"
        :title="editingProject.name"
        @ok="handleUpdateProject"
        @cancel="showProjectDetailsModal = false"
      >
        <div v-if="editingProject.id" class="space-y-4">
          <a-descriptions bordered :column="1" size="small">
            <a-descriptions-item :label="$t('projects.projectId')">
              {{ editingProject.id }}
            </a-descriptions-item>
            <a-descriptions-item :label="$t('projects.created')">
              {{ formatDate(editingProject.createdAt) }}
            </a-descriptions-item>
          </a-descriptions>

          <a-form layout="vertical" class="mt-4">
            <a-form-item :label="$t('projects.name')" required>
              <a-input v-model:value="editingProject.name" />
            </a-form-item>
            <a-form-item :label="$t('projects.description')">
              <a-textarea v-model:value="editingProject.description" :rows="3" />
            </a-form-item>
            <a-form-item :label="$t('projects.status')">
              <a-select v-model:value="editingProject.status">
                <a-select-option value="active">{{ $t("projects.active") }}</a-select-option>
                <a-select-option value="completed">{{ $t("projects.completed") }}</a-select-option>
                <a-select-option value="archived">{{ $t("projects.archived") }}</a-select-option>
              </a-select>
            </a-form-item>
          </a-form>
        </div>
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
                :key="project.id"
                :value="project.id"
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
const isLoadingProjects = ref(false);

const showCreateProjectModal = ref(false);
const showProjectDetailsModal = ref(false);
const showCreateWorkItemModal = ref(false);
const showEditWorkItemModal = ref(false);

const newProject = ref({
  name: "",
  description: "",
});

const editingProject = ref<Partial<Project>>({});

const newWorkItem = ref({
  projectId: 0,
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
      await fetchProjects();
    }
  } catch (error) {
    console.error("Failed to create work item:", error);
    message.error(t("workItems.createError"));
  }
};

const viewEditProjectDetails = (project: Project) => {
  editingProject.value = { ...project };
  showProjectDetailsModal.value = true;
};

const handleUpdateProject = async () => {
  if (!editingProject.value.id) return;

  try {
    const response = await $fetch(`/api/projects/${editingProject.value.id}`, {
      method: "PUT",
      body: {
        name: editingProject.value.name,
        description: editingProject.value.description,
        status: editingProject.value.status,
      },
    });

    if (response.success) {
      message.success(t("projects.updateSuccess"));
      showProjectDetailsModal.value = false;
      await fetchProjects();
    }
  } catch (error) {
    console.error("Failed to update project:", error);
    message.error(t("projects.updateError"));
  }
};

const deleteProject = async (id: number) => {
  try {
    const response = await $fetch(`/api/projects/${id}`, {
      method: "DELETE",
    });

    if (response.success) {
      message.success(t("projects.deleteSuccess"));
      await fetchProjects();
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
  if (!editingWorkItem.value.id) return;

  try {
    const response = await $fetch(`/api/work-items/${editingWorkItem.value.id}`, {
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
      await fetchProjects();
    }
  } catch (error) {
    console.error("Failed to update work item:", error);
    message.error(t("workItems.updateError"));
  }
};

const deleteWorkItem = async (id: number) => {
  try {
    const response = await $fetch(`/api/work-items/${id}`, {
      method: "DELETE",
    });

    if (response.success) {
      message.success(t("workItems.deleteSuccess"));
      await fetchProjects();
    }
  } catch (error) {
    console.error("Failed to delete work item:", error);
    message.error(t("workItems.deleteError"));
  }
};

const openWorkItem = (id: number) => {
  router.push(`/work-items/${id}`);
};

const manageProjectDatasets = (id: number) => {
  router.push(`/project/${id}/datasets`);
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
    projectId: 0,
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

const formatDate = (dateString: string): string => {
  if (!dateString) return "";
  const date = new Date(dateString);
  return date.toLocaleString();
};

onMounted(() => {
  fetchProjects();
});
</script>
