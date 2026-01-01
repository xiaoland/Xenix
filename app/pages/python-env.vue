<template>
  <div class="min-h-screen bg-gray-50 py-8">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <PageHeader />
      <a-card :title="$t('pythonEnv.title')" class="env-card">
        <a-descriptions bordered :column="1" size="small">
          <a-descriptions-item :label="$t('pythonEnv.pdmInstalled')">
            <a-tag :color="envStatus.pdmInstalled ? 'success' : 'error'">
              {{
                envStatus.pdmInstalled
                  ? $t("pythonEnv.yes")
                  : $t("pythonEnv.no")
              }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item :label="$t('pythonEnv.envReady')">
            <a-tag :color="envStatus.envReady ? 'success' : 'warning'">
              {{
                envStatus.envReady ? $t("pythonEnv.yes") : $t("pythonEnv.no")
              }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item :label="$t('pythonEnv.initialized')">
            <a-tag :color="envStatus.initialized ? 'success' : 'default'">
              {{
                envStatus.initialized ? $t("pythonEnv.yes") : $t("pythonEnv.no")
              }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item :label="$t('pythonEnv.pyPackagesDir')">
            <a-tag :color="envStatus.pyPackagesExists ? 'success' : 'default'">
              {{
                envStatus.pyPackagesExists
                  ? $t("pythonEnv.exists")
                  : $t("pythonEnv.notFound")
              }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item :label="$t('pythonEnv.pdmLockFile')">
            <a-tag :color="envStatus.pdmLockExists ? 'success' : 'default'">
              {{
                envStatus.pdmLockExists
                  ? $t("pythonEnv.exists")
                  : $t("pythonEnv.notFound")
              }}
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
              {{ $t("pythonEnv.refreshStatus") }}
            </a-button>
            <a-button
              :loading="setupLoading"
              @click="setupEnvironment"
              class="inline-flex items-center"
            >
              <template #icon><span class="i-mdi-cog" /></template>
              {{ $t("pythonEnv.setupEnvironment") }}
            </a-button>
            <a-button
              danger
              :loading="reinstallLoading"
              @click="reinstallEnvironment"
              class="inline-flex items-center"
            >
              <template #icon><span class="i-mdi-download" /></template>
              {{ $t("pythonEnv.reinstallDependencies") }}
            </a-button>
            <a-button
              type="default"
              :loading="syncLoading"
              @click="syncModels"
              class="inline-flex items-center"
            >
              <template #icon><span class="i-mdi-sync" /></template>
              {{ $t("pythonEnv.syncModels") }}
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
          <h4>{{ $t("pythonEnv.logsTitle") }}</h4>
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
import { useI18n } from "vue-i18n";
import PageHeader from "~/components/common/PageHeader.vue";

const { t } = useI18n();

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
const syncLoading = ref(false);
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
      message.value = t("pythonEnv.statusRefreshed");
      messageType.value = "success";
    }
  } catch (error) {
    message.value = t("pythonEnv.fetchStatusFailed", { error: error.message });
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
    logs.value.push(t("pythonEnv.logStartingSetup"));
    const response = await $fetch("/api/pythonEnv/setup", { method: "POST" });

    if (response.success) {
      envStatus.value = response.status;
      message.value = t("pythonEnv.setupCompleted");
      messageType.value = "success";
      logs.value.push(t("pythonEnv.logSetupSuccess"));
    }
  } catch (error) {
    message.value = t("pythonEnv.setupFailed", { error: error.message });
    messageType.value = "error";
    logs.value.push(t("pythonEnv.logError", { error: error.message }));
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
    logs.value.push(t("pythonEnv.logStartingReinstall"));
    logs.value.push(t("pythonEnv.logReinstallNote"));

    const response = await $fetch("/api/pythonEnv/reinstall", {
      method: "POST",
    });

    if (response.success) {
      envStatus.value = response.status;
      message.value = t("pythonEnv.reinstallCompleted");
      messageType.value = "success";
      logs.value.push(t("pythonEnv.logReinstallSuccess"));
    }
  } catch (error) {
    message.value = t("pythonEnv.reinstallFailed", { error: error.message });
    messageType.value = "error";
    logs.value.push(t("pythonEnv.logError", { error: error.message }));
    console.error("Error reinstalling environment:", error);
  } finally {
    reinstallLoading.value = false;
    await refreshStatus();
  }
};

const syncModels = async () => {
  syncLoading.value = true;
  message.value = "";
  logs.value = [];

  try {
    logs.value.push(t("pythonEnv.logStartingSync"));
    const response = await $fetch("/api/sync-models", { method: "POST" });

    if (response.success) {
      message.value = response.message;
      messageType.value = "success";
      logs.value.push(
        t("pythonEnv.logSyncSuccess", { message: response.message })
      );
    }
  } catch (error) {
    message.value = t("pythonEnv.syncFailed", { error: error.message });
    messageType.value = "error";
    logs.value.push(t("pythonEnv.logError", { error: error.message }));
    console.error("Error syncing models:", error);
  } finally {
    syncLoading.value = false;
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
