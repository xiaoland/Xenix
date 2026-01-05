<template>
  <div
    class="flex items-center justify-between p-2 bg-gray-50 rounded hover:bg-gray-100 cursor-pointer transition-colors"
    @click="handleClick"
  >
    <div class="flex items-center gap-2 flex-1">
      <span class="i-mdi-file-document-outline text-green-500"></span>
      <span class="font-medium">{{ workItem.name }}</span>
      <a-tag
        size="small"
        :color="statusColor"
      >
        {{ workItem.status || 'active' }}
      </a-tag>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useRouter } from 'vue-router';
import type { WorkItem } from '@xenix/shared';

interface Props {
  workItem: WorkItem;
}

const props = defineProps<Props>();

const router = useRouter();

const statusColor = computed(() => {
  switch (props.workItem.status) {
    case 'active':
      return 'green';
    case 'completed':
      return 'blue';
    case 'archived':
      return 'gray';
    default:
      return 'default';
  }
});

const handleClick = () => {
  router.push(`/work-items/${props.workItem.id}`);
};
</script>
