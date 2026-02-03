<template>
  <default-layout>
    <div class="max-w-7xl mx-auto px-4 py-8">
      <a-breadcrumb class="mb-6">
        <a-breadcrumb-item>
          <router-link to="/">{{ $t("navigation.home") }}</router-link>
        </a-breadcrumb-item>
        <a-breadcrumb-item>
          <router-link :to="`/projects/${projectId}/datasets`">
            {{ $t("datasets.title") }}
          </router-link>
        </a-breadcrumb-item>
        <a-breadcrumb-item v-if="dataset">{{ dataset.name }}</a-breadcrumb-item>
      </a-breadcrumb>

      <div v-if="loading" class="text-center py-12">
        <a-spin size="large" />
      </div>

      <div v-else-if="error" class="text-center py-12">
        <a-result
          status="404"
          :title="$t('datasets.notFound')"
          :sub-title="$t('datasets.notFoundDescription')"
        >
          <template #extra>
            <a-button type="primary" @click="router.push(`/projects/${projectId}/datasets`)">
              {{ $t("datasets.backToList") }}
            </a-button>
          </template>
        </a-result>
      </div>

      <div v-else-if="dataset">
        <div class="mb-8">
          <h1 class="text-3xl font-bold mb-2">{{ dataset.name }}</h1>
          <p v-if="dataset.filePath" class="text-gray-600 mb-3">
            <strong>File:</strong> {{ dataset.filePath.split("/").pop() }}
          </p>
          <p v-if="dataset.createdAt" class="text-sm text-gray-500">
            <strong>Uploaded:</strong> {{ new Date(dataset.createdAt).toLocaleDateString() }}
          </p>
        </div>

        <a-card>
          <h3 class="text-lg font-semibold mb-4">
            {{ $t("datasets.columns") }} ({{ dataset.columns.length }})
          </h3>
          <div class="flex flex-wrap gap-2">
            <a-tag v-for="col in dataset.columns" :key="col">
              {{ col }}
            </a-tag>
          </div>

          <div v-if="dataset.filePath" class="mt-6">
            <h3 class="text-lg font-semibold mb-2">{{ $t("datasets.filePath") }}</h3>
            <p class="text-sm text-gray-600">{{ dataset.filePath }}</p>
          </div>
        </a-card>
      </div>
    </div>
  </default-layout>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";

import DefaultLayout from "../../common/components/DefaultLayout.vue";
import { useDataset } from "../queries";

interface Dataset {
  id: number;
  name: string;
  filePath?: string;
  columns: string[];
  createdAt?: string;
}

const route = useRoute();
const router = useRouter();
const projectId = Number(route.params.projectId);
const datasetId = computed(() => Number(route.params.id));

const { data: datasetData, isLoading: loading, error: fetchError } = useDataset(datasetId);

const dataset = computed((): Dataset | undefined => {
  if (!datasetData.value) return undefined;
  return datasetData.value as Dataset;
});

const error = computed(() => !!fetchError.value);
</script>
