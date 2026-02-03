<template>
  <div class="error-state">
    <div class="error-icon">
      <slot name="icon">
        <span class="i-mdi-close-circle-outline" />
      </slot>
    </div>
    <h4 v-if="title" class="error-title">{{ title }}</h4>
    <p v-if="description" class="error-description">{{ description }}</p>
    <p v-if="error" class="error-message">{{ error.message }}</p>
    <div v-if="$slots.action || showRetry" class="error-action">
      <slot name="action">
        <a-button v-if="showRetry" type="primary" @click="$emit('retry')">
          {{ retryText || $t("common.retry") }}
        </a-button>
      </slot>
    </div>
  </div>
</template>

<script setup lang="ts">
interface Props {
  /** Error object */
  error?: Error | null;
  /** Title text */
  title?: string;
  /** Description text */
  description?: string;
  /** Show retry button */
  showRetry?: boolean;
  /** Retry button text */
  retryText?: string;
}

withDefaults(defineProps<Props>(), {
  error: null,
  showRetry: true,
});

defineEmits<{
  retry: [];
}>();
</script>

<style scoped lang="scss">
.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 24px;
  text-align: center;
}

.error-icon {
  font-size: 64px;
  color: var(--color-error);
  margin-bottom: 16px;
}

.error-title {
  font-size: 18px;
  font-weight: 500;
  color: var(--color-text);
  margin-bottom: 8px;
}

.error-description {
  color: var(--color-text-secondary);
  max-width: 400px;
  margin-bottom: 8px;
}

.error-message {
  color: var(--color-error);
  font-size: 14px;
  margin-bottom: 24px;
  padding: 12px 16px;
  background: var(--color-error-light);
  border-radius: var(--radius-md);
  max-width: 500px;
}

.error-action {
  margin-top: 8px;
}
</style>
