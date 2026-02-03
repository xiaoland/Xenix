<template>
  <div class="empty-state" :class="`empty-state--${type}`">
    <div class="empty-icon">
      <slot name="icon">
        <span :class="iconClass" />
      </slot>
    </div>
    <h4 v-if="title" class="empty-title">{{ title }}</h4>
    <p v-if="description" class="empty-description">{{ description }}</p>
    <div v-if="$slots.action" class="empty-action">
      <slot name="action" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";

interface Props {
  /** Empty state type */
  type?: "default" | "search" | "data" | "error" | "info";
  /** Title text */
  title?: string;
  /** Description text */
  description?: string;
}

const props = withDefaults(defineProps<Props>(), {
  type: "default",
});

const iconClass = computed(() => {
  switch (props.type) {
    case "search":
      return "i-mdi-magnify";
    case "data":
      return "i-mdi-file-outline";
    case "error":
      return "i-mdi-alert-outline";
    case "info":
      return "i-mdi-information-outline";
    default:
      return "i-mdi-inbox-outline";
  }
});
</script>

<style scoped lang="scss">
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 24px;
  text-align: center;
}

.empty-icon {
  font-size: 64px;
  color: var(--color-text-disabled);
  margin-bottom: 16px;
}

.empty-title {
  font-size: 16px;
  font-weight: 500;
  color: var(--color-text);
  margin-bottom: 8px;
}

.empty-description {
  color: var(--color-text-secondary);
  max-width: 400px;
  margin-bottom: 24px;
}

.empty-action {
  margin-top: 8px;
}
</style>
