<template>
  <div class="min-h-screen bg-gray-50 py-8 overflow-x-hidden">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <PageHeader />

      <div class="text-center mb-4">
        <a-breadcrumb>
          <a-breadcrumb-item>
            <NuxtLink to="/">{{ $t("navigation.home") }}</NuxtLink>
          </a-breadcrumb-item>
          <a-breadcrumb-item>
            <NuxtLink :to="`/work-items/${workItemId}`">{{
              workItem?.name || "Work Item"
            }}</NuxtLink>
          </a-breadcrumb-item>
          <a-breadcrumb-item>{{ $t("prediction.history") }}</a-breadcrumb-item>
        </a-breadcrumb>
      </div>

      <div v-if="isLoading" class="text-center py-8">
        <a-spin size="large" />
      </div>

      <div v-else-if="!workItem" class="text-center py-8">
        <a-result
          status="404"
          :title="$t('workItems.fetchError')"
          :sub-title="$t('workItems.fetchError')"
        >
          <template #extra>
            <a-button type="primary" @click="$router.push('/')">
              {{ $t("navigation.home") }}
            </a-button>
          </template>
        </a-result>
      </div>

      <div v-else>
        <div class="text-center mb-8">
          <h1 class="text-4xl font-bold text-gray-900 mb-2">
            {{ $t("prediction.history") }}
          </h1>
          <p class="text-lg text-gray-600">
            {{ $t("prediction.historyDescription") }}
          </p>
          <div class="mt-2">
            <a-tag :color="getStatusColor(workItem.status)">
              {{ $t(`workItems.${workItem.status}`) }}
            </a-tag>
          </div>
        </div>

        <a-card>
          <PredictionHistory :work-item-id="workItemId" />
        </a-card>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRoute } from "vue-router";
import { message } from "ant-design-vue";
import { useI18n } from "vue-i18n";
import { WorkItemService } from "~/services";
import PageHeader from "~/components/common/PageHeader.vue";
import PredictionHistory from "~/components/ml/prediction/PredictionHistory.vue";
import type { WorkItem } from "~/types";

const { t } = useI18n();
const route = useRoute();

// Work item data
const workItem = ref<WorkItem | null>(null);
const isLoading = ref(false);
const workItemId = Number(route.params.id);

const fetchWorkItem = async () => {
  isLoading.value = true;
  try {
    const response = await WorkItemService.fetchById(workItemId);
    if (response.success) {
      workItem.value = response.workItem;
    } else {
      message.error(t("workItems.fetchError"));
    }
  } catch (error) {
    console.error("Failed to fetch work item:", error);
    message.error(t("workItems.fetchError"));
  } finally {
    isLoading.value = false;
  }
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

onMounted(() => {
  fetchWorkItem();
});
</script>
