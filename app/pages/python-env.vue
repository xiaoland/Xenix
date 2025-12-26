<template>
  <div class="min-h-screen bg-gray-50 py-8">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <PageHeader />
      <a-card title="Python Environment Management" class="env-card">
        <a-descriptions bordered :column="1" size="small">
          <a-descriptions-item label="PDM Installed">
            <a-tag :color="envStatus.pdmInstalled ? 'success' : 'error'">
              {{ envStatus.pdmInstalled ? "Yes" : "No" }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="Environment Ready">
            <a-tag :color="envStatus.envReady ? 'success' : 'warning'">
              {{ envStatus.envReady ? "Yes" : "No" }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="Initialized">
            <a-tag :color="envStatus.initialized ? 'success' : 'default'">
              {{ envStatus.initialized ? "Yes" : "No" }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="__pypackages__ Directory">
            <a-tag :color="envStatus.pyPackagesExists ? 'success' : 'default'">
              {{ envStatus.pyPackagesExists ? "Exists" : "Not Found" }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="pdm.lock File">
            <a-tag :color="envStatus.pdmLockExists ? 'success' : 'default'">
              {{ envStatus.pdmLockExists ? "Exists" : "Not Found" }}
            </a-tag>
          </a-descriptions-item>
        </a-descriptions>

        <div class="actions" style="margin-top: 24px">
          <a-space>
            <a-button
              type="primary"
              :loading="loading"
              @click="refreshStatus"
              class="inline-flex items-center"
            >
              <template #icon><span class="i-mdi-refresh" /></template>
              Refresh Status
            </a-button>
            <a-button
              :loading="setupLoading"
              @click="setupEnvironment"
              class="inline-flex items-center"
            >
              <template #icon><span class="i-mdi-cog" /></template>
              Setup Environment
            </a-button>
            <a-button
              danger
              :loading="reinstallLoading"
              @click="reinstallEnvironment"
              class="inline-flex items-center"
            >
              <template #icon><span class="i-mdi-download" /></template>
              Reinstall Dependencies
            </a-button>
          </a-space>
        </div>

        <a-alert
          v-if="message"
          :message="message"
          :type="messageType"
          show-icon
          closable
          style="margin-top: 16px"
          @close="message = ''"
        />

        <div v-if="logs.length > 0" class="logs" style="margin-top: 24px">
          <h4>Environment Logs:</h4>
          <a-textarea
            :value="logs.join('\n')"
            :rows="10"
            readonly
            style="font-family: monospace; font-size: 12px"
          />
        </div>
      </a-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";

interface EnvStatus {
  pdmInstalled: boolean;
  envReady: boolean;
  initialized: boolean;
  pyPackagesExists: boolean;
  pdmLockExists: boolean;
}

const envStatus = ref<EnvStatus>({
  pdmInstalled: false,
  envReady: false,
  initialized: false,
  pyPackagesExists: false,
  pdmLockExists: false,
});

const loading = ref(false);
const setupLoading = ref(false);
const reinstallLoading = ref(false);
const message = ref("");
const messageType = ref<"success" | "info" | "warning" | "error">("info");
const logs = ref<string[]>([]);

const refreshStatus = async () => {
  loading.value = true;
  message.value = "";

  try {
    const response = await $fetch("/api/pythonEnv/status");
    if (response.success) {
      envStatus.value = response.status;
      message.value = "Status refreshed successfully";
      messageType.value = "success";
    }
  } catch (error) {
    message.value = `Failed to fetch status: ${error.message}`;
    messageType.value = "error";
    console.error("Error fetching environment status:", error);
  } finally {
    loading.value = false;
  }
};

const setupEnvironment = async () => {
  setupLoading.value = true;
  message.value = "";
  logs.value = [];

  try {
    logs.value.push("[INFO] Starting environment setup...");
    const response = await $fetch("/api/pythonEnv/setup", { method: "POST" });

    if (response.success) {
      envStatus.value = response.status;
      message.value = "Environment setup completed successfully";
      messageType.value = "success";
      logs.value.push("[SUCCESS] Environment setup completed");
    }
  } catch (error) {
    message.value = `Failed to setup environment: ${error.message}`;
    messageType.value = "error";
    logs.value.push(`[ERROR] ${error.message}`);
    console.error("Error setting up environment:", error);
  } finally {
    setupLoading.value = false;
    await refreshStatus();
  }
};

const reinstallEnvironment = async () => {
  reinstallLoading.value = true;
  message.value = "";
  logs.value = [];

  try {
    logs.value.push("[INFO] Starting environment reinstallation...");
    logs.value.push("[INFO] This may take a few minutes...");

    const response = await $fetch("/api/pythonEnv/reinstall", {
      method: "POST",
    });

    if (response.success) {
      envStatus.value = response.status;
      message.value = "Environment reinstalled successfully";
      messageType.value = "success";
      logs.value.push("[SUCCESS] Environment reinstallation completed");
    }
  } catch (error) {
    message.value = `Failed to reinstall environment: ${error.message}`;
    messageType.value = "error";
    logs.value.push(`[ERROR] ${error.message}`);
    console.error("Error reinstalling environment:", error);
  } finally {
    reinstallLoading.value = false;
    await refreshStatus();
  }
};

onMounted(() => {
  refreshStatus();
});
</script>

<style scoped lang="scss">
.env-card {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.actions {
  display: flex;
  gap: 12px;
}

.logs {
  h4 {
    margin-bottom: 8px;
    font-weight: 600;
  }
}
</style>
