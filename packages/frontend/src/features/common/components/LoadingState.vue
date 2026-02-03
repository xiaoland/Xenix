<template>
  <div
    class="loading-state"
    :class="{ 'loading-state--fullscreen': fullscreen }"
  >
    <a-spin :size="size" :tip="tip">
      <template #indicator>
        <slot name="indicator">
          <span class="i-mdi-loading animate-spin" :style="indicatorStyle" />
        </slot>
      </template>
    </a-spin>
    <p v-if="description" class="loading-description">{{ description }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";

interface Props {
  /** Loading size */
  size?: "small" | "default" | "large";
  /** Loading tip text */
  tip?: string;
  /** Additional description below spinner */
  description?: string;
  /** Full screen overlay */
  fullscreen?: boolean;
  /** Custom indicator size in pixels */
  indicatorSize?: number;
}

const props = withDefaults(defineProps<Props>(), {
  size: "default",
  fullscreen: false,
  indicatorSize: undefined,
});

const indicatorStyle = computed(() => {
  if (props.indicatorSize) {
    return { fontSize: `${props.indicatorSize}px` };
  }
  return undefined;
});
</script>

<style scoped lang="scss">
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 24px;

  &--fullscreen {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(255, 255, 255, 0.8);
    z-index: var(--z-modal);
  }
}

.loading-description {
  margin-top: 16px;
  color: var(--color-text-secondary);
}
</style>
