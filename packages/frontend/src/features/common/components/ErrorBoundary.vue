<template>
  <slot v-if="hasError" name="error" :error="error" :reset="reset">
    <div class="error-boundary">
      <div class="error-content">
        <div class="error-icon">
          <span class="i-mdi-alert-circle-outline" />
        </div>
        <h3 class="error-title">{{ $t("error.boundary.title") }}</h3>
        <p class="error-message">{{ displayError }}</p>
        <div class="error-actions">
          <a-button type="primary" @click="reset">
            {{ $t("error.boundary.retry") }}
          </a-button>
          <a-button v-if="showDetails" @click="toggleDetails">
            {{
              showErrorDetails
                ? $t("error.boundary.hideDetails")
                : $t("error.boundary.showDetails")
            }}
          </a-button>
        </div>
        <pre v-if="showErrorDetails && error" class="error-details">{{
          error.stack
        }}</pre>
      </div>
    </div>
  </slot>
  <slot v-else />
</template>

<script setup lang="ts">
import { computed, onErrorCaptured, ref } from "vue";
import { useI18n } from "vue-i18n";

const { t } = useI18n();

interface Props {
  /** Show detailed error information (stack trace) */
  showDetails?: boolean;
  /** Callback when error is captured */
  onError?: (error: Error) => void;
}

const props = withDefaults(defineProps<Props>(), {
  showDetails: false,
});

const hasError = ref(false);
const error = ref<Error | null>(null);
const showErrorDetails = ref(false);

const displayError = computed(() => {
  if (!error.value) return t("error.boundary.unknown");
  return error.value.message || t("error.boundary.unknown");
});

function toggleDetails() {
  showErrorDetails.value = !showErrorDetails.value;
}

function reset() {
  hasError.value = false;
  error.value = null;
  showErrorDetails.value = false;
}

onErrorCaptured((err: unknown) => {
  hasError.value = true;
  error.value = err instanceof Error ? err : new Error(String(err));

  if (props.onError) {
    props.onError(error.value);
  }

  // Prevent error from propagating
  return false;
});
</script>

<style scoped lang="scss">
.error-boundary {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 300px;
  padding: 24px;
}

.error-content {
  text-align: center;
  max-width: 500px;
}

.error-icon {
  font-size: 48px;
  color: var(--color-error);
  margin-bottom: 16px;
}

.error-title {
  font-size: 20px;
  font-weight: 600;
  margin-bottom: 8px;
  color: var(--color-text);
}

.error-message {
  color: var(--color-text-secondary);
  margin-bottom: 24px;
}

.error-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
  margin-bottom: 16px;
}

.error-details {
  text-align: left;
  background: var(--color-background-light);
  padding: 16px;
  border-radius: var(--radius-md);
  font-size: 12px;
  overflow-x: auto;
  color: var(--color-text-secondary);
  margin-top: 16px;
}
</style>
