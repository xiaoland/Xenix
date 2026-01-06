import { ref, onMounted, onUnmounted } from 'vue';
import { message } from 'ant-design-vue';
import { client } from '../../../api/client';
import { AVAILABLE_MODELS } from '../../../constants/models';
const props = defineProps();
const emit = defineEmits();
// State
const selectedModels = ref([]);
const tasks = ref([]);
const selectedTaskId = ref(null);
const loading = ref(false);
const isTraining = ref(false);
// Available models
const availableModels = AVAILABLE_MODELS.map(m => ({
    label: m.label,
    value: m.value,
}));
// Table columns
const columns = [
    { title: 'Model', key: 'model', width: 200 },
    { title: 'Status', key: 'status', width: 120 },
    { title: 'Metrics / Error', key: 'metrics' },
    { title: 'Action', key: 'action', width: 100 },
];
// Polling interval
let pollInterval = null;
/**
 * Fetch tuning tasks for the work item
 */
const fetchTasks = async () => {
    loading.value = true;
    try {
        const response = await client.api.tasks.$get({
            query: {
                workItemId: String(props.workItemId),
                types: 'auto-tune,manual-tune',
            },
        });
        if (response.ok) {
            const data = await response.json();
            tasks.value = data.tasks || [];
        }
    }
    catch (error) {
        console.error('Failed to fetch tasks:', error);
    }
    finally {
        loading.value = false;
    }
};
/**
 * Start auto-tune for selected models
 */
const handleStartAutoTune = async () => {
    isTraining.value = true;
    try {
        // Start training for each selected model
        for (const model of selectedModels.value) {
            await TuneService.startAutoTune({
                datasetId: props.datasetId,
                features: props.featureColumns,
                target: props.targetColumn,
                model,
                workItemId: props.workItemId,
            });
        }
        message.success(`Started training for ${selectedModels.value.length} model(s)`);
        selectedModels.value = [];
        await fetchTasks();
        startPolling();
    }
    catch (error) {
        console.error('Failed to start training:', error);
        message.error(error.message || 'Failed to start training');
    }
    finally {
        isTraining.value = false;
    }
};
/**
 * Clear all failed tasks
 */
const handleClearFailedTasks = async () => {
    try {
        await TaskService.deleteFailedTasks(props.workItemId);
        message.success('Failed tasks cleared');
        await fetchTasks();
    }
    catch (error) {
        console.error('Failed to clear tasks:', error);
        message.error(error.message || 'Failed to clear tasks');
    }
};
/**
 * Select a task to continue
 */
const handleSelectTask = (taskId) => {
    selectedTaskId.value = taskId;
};
/**
 * Continue to prediction step
 */
const handleContinue = async () => {
    if (!selectedTaskId.value)
        return;
    try {
        const response = await TaskService.fetchStatus(selectedTaskId.value);
        if (response.task) {
            emit('continue', {
                model: response.task.parameter?.model || '',
                parameters: response.task.result?.params || {},
                taskId: selectedTaskId.value,
            });
        }
    }
    catch (error) {
        console.error('Failed to fetch task:', error);
        message.error(error.message || 'Failed to fetch task details');
    }
};
/**
 * Start polling for task updates
 */
const startPolling = () => {
    if (pollInterval)
        return;
    pollInterval = window.setInterval(() => {
        const hasRunningTasks = tasks.value.some(t => t.status === 'pending' || t.status === 'running');
        if (hasRunningTasks) {
            fetchTasks();
        }
        else {
            stopPolling();
        }
    }, 3000);
};
/**
 * Stop polling
 */
const stopPolling = () => {
    if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
    }
};
/**
 * Get status color
 */
const getStatusColor = (status) => {
    switch (status) {
        case 'completed': return 'success';
        case 'failed': return 'error';
        case 'running': return 'processing';
        case 'pending': return 'default';
        default: return 'default';
    }
};
/**
 * Format model name
 */
const formatModelName = (modelValue) => {
    if (!modelValue)
        return '-';
    const model = AVAILABLE_MODELS.find(m => m.value === modelValue);
    return model ? model.label : modelValue;
};
/**
 * Format metric value
 */
const formatMetric = (value) => {
    if (typeof value === 'number') {
        return value.toFixed(4);
    }
    return value;
};
/**
 * Get display metrics from result
 */
const getDisplayMetrics = (result) => {
    if (!result || !result.params)
        return {};
    // Show a subset of important metrics
    const metrics = {};
    if (result.score !== undefined)
        metrics['Score'] = result.score;
    if (result.params) {
        const paramCount = Object.keys(result.params).length;
        metrics['Parameters'] = `${paramCount} params`;
    }
    return metrics;
};
// Lifecycle
onMounted(async () => {
    await fetchTasks();
    const hasRunningTasks = tasks.value.some(t => t.status === 'pending' || t.status === 'running');
    if (hasRunningTasks) {
        startPolling();
    }
});
onUnmounted(() => {
    stopPolling();
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "space-y-6" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({
    ...{ class: "text-2xl font-semibold mb-4" },
});
const __VLS_0 = {}.AAlert;
/** @type {[typeof __VLS_components.AAlert, typeof __VLS_components.aAlert, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    message: "Train machine learning models",
    description: "Select models and configure hyperparameters to train on your dataset. Select a completed task to continue to predictions.",
    type: "info",
    showIcon: true,
    ...{ class: "mb-4" },
}));
const __VLS_2 = __VLS_1({
    message: "Train machine learning models",
    description: "Select models and configure hyperparameters to train on your dataset. Select a completed task to continue to predictions.",
    type: "info",
    showIcon: true,
    ...{ class: "mb-4" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "bg-white rounded-lg border p-4 mb-4" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
    ...{ class: "text-lg font-medium mb-3" },
});
const __VLS_4 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
    value: (__VLS_ctx.selectedModels),
    mode: "multiple",
    placeholder: "Select models to train",
    ...{ style: {} },
    options: (__VLS_ctx.availableModels),
    ...{ class: "mb-3" },
}));
const __VLS_6 = __VLS_5({
    value: (__VLS_ctx.selectedModels),
    mode: "multiple",
    placeholder: "Select models to train",
    ...{ style: {} },
    options: (__VLS_ctx.availableModels),
    ...{ class: "mb-3" },
}, ...__VLS_functionalComponentArgsRest(__VLS_5));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex gap-2" },
});
const __VLS_8 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
    ...{ 'onClick': {} },
    type: "primary",
    ...{ class: "inline-flex items-center" },
    loading: (__VLS_ctx.isTraining),
    disabled: (__VLS_ctx.selectedModels.length === 0),
}));
const __VLS_10 = __VLS_9({
    ...{ 'onClick': {} },
    type: "primary",
    ...{ class: "inline-flex items-center" },
    loading: (__VLS_ctx.isTraining),
    disabled: (__VLS_ctx.selectedModels.length === 0),
}, ...__VLS_functionalComponentArgsRest(__VLS_9));
let __VLS_12;
let __VLS_13;
let __VLS_14;
const __VLS_15 = {
    onClick: (__VLS_ctx.handleStartAutoTune)
};
__VLS_11.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "i-mdi-auto-fix mr-1" },
});
var __VLS_11;
const __VLS_16 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
    ...{ 'onClick': {} },
    disabled: (__VLS_ctx.tasks.length === 0),
    danger: true,
    ...{ class: "inline-flex items-center" },
}));
const __VLS_18 = __VLS_17({
    ...{ 'onClick': {} },
    disabled: (__VLS_ctx.tasks.length === 0),
    danger: true,
    ...{ class: "inline-flex items-center" },
}, ...__VLS_functionalComponentArgsRest(__VLS_17));
let __VLS_20;
let __VLS_21;
let __VLS_22;
const __VLS_23 = {
    onClick: (__VLS_ctx.handleClearFailedTasks)
};
__VLS_19.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "i-mdi-delete-outline mr-1" },
});
var __VLS_19;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "bg-white rounded-lg border" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "px-4 py-3 border-b bg-gray-50" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
    ...{ class: "text-lg font-medium" },
});
const __VLS_24 = {}.ATable;
/** @type {[typeof __VLS_components.ATable, typeof __VLS_components.aTable, typeof __VLS_components.ATable, typeof __VLS_components.aTable, ]} */ ;
// @ts-ignore
const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
    columns: (__VLS_ctx.columns),
    dataSource: (__VLS_ctx.tasks),
    loading: (__VLS_ctx.loading),
    pagination: (false),
    rowKey: "id",
    size: "small",
}));
const __VLS_26 = __VLS_25({
    columns: (__VLS_ctx.columns),
    dataSource: (__VLS_ctx.tasks),
    loading: (__VLS_ctx.loading),
    pagination: (false),
    rowKey: "id",
    size: "small",
}, ...__VLS_functionalComponentArgsRest(__VLS_25));
__VLS_27.slots.default;
{
    const { bodyCell: __VLS_thisSlot } = __VLS_27.slots;
    const [{ column, record }] = __VLS_getSlotParams(__VLS_thisSlot);
    if (column.key === 'model') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "font-medium" },
        });
        (__VLS_ctx.formatModelName(record.parameter?.model));
    }
    else if (column.key === 'status') {
        const __VLS_28 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({
            color: (__VLS_ctx.getStatusColor(record.status)),
        }));
        const __VLS_30 = __VLS_29({
            color: (__VLS_ctx.getStatusColor(record.status)),
        }, ...__VLS_functionalComponentArgsRest(__VLS_29));
        __VLS_31.slots.default;
        (record.status);
        var __VLS_31;
    }
    else if (column.key === 'metrics') {
        if (record.status === 'completed' && record.result?.params) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "text-sm" },
            });
            for (const [value, key] of __VLS_getVForSourceType((__VLS_ctx.getDisplayMetrics(record.result)))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    key: (key),
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "text-gray-600" },
                });
                (key);
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "ml-1 font-medium" },
                });
                (__VLS_ctx.formatMetric(value));
            }
        }
        else if (record.status === 'failed') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "text-red-500 text-sm" },
            });
            (record.error || 'Training failed');
        }
        else {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "text-gray-400 text-sm" },
            });
        }
    }
    else if (column.key === 'action') {
        const __VLS_32 = {}.ARadio;
        /** @type {[typeof __VLS_components.ARadio, typeof __VLS_components.aRadio, typeof __VLS_components.ARadio, typeof __VLS_components.aRadio, ]} */ ;
        // @ts-ignore
        const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
            ...{ 'onClick': {} },
            checked: (__VLS_ctx.selectedTaskId === record.id),
            disabled: (record.status !== 'completed'),
        }));
        const __VLS_34 = __VLS_33({
            ...{ 'onClick': {} },
            checked: (__VLS_ctx.selectedTaskId === record.id),
            disabled: (record.status !== 'completed'),
        }, ...__VLS_functionalComponentArgsRest(__VLS_33));
        let __VLS_36;
        let __VLS_37;
        let __VLS_38;
        const __VLS_39 = {
            onClick: (...[$event]) => {
                if (!!(column.key === 'model'))
                    return;
                if (!!(column.key === 'status'))
                    return;
                if (!!(column.key === 'metrics'))
                    return;
                if (!(column.key === 'action'))
                    return;
                __VLS_ctx.handleSelectTask(record.id);
            }
        };
        __VLS_35.slots.default;
        var __VLS_35;
    }
}
var __VLS_27;
if (__VLS_ctx.tasks.length === 0 && !__VLS_ctx.loading) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-center py-8 text-gray-500" },
    });
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex justify-between" },
});
const __VLS_40 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
    ...{ 'onClick': {} },
}));
const __VLS_42 = __VLS_41({
    ...{ 'onClick': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_41));
let __VLS_44;
let __VLS_45;
let __VLS_46;
const __VLS_47 = {
    onClick: (...[$event]) => {
        __VLS_ctx.emit('back');
    }
};
__VLS_43.slots.default;
var __VLS_43;
const __VLS_48 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
    ...{ 'onClick': {} },
    type: "primary",
    disabled: (!__VLS_ctx.selectedTaskId),
}));
const __VLS_50 = __VLS_49({
    ...{ 'onClick': {} },
    type: "primary",
    disabled: (!__VLS_ctx.selectedTaskId),
}, ...__VLS_functionalComponentArgsRest(__VLS_49));
let __VLS_52;
let __VLS_53;
let __VLS_54;
const __VLS_55 = {
    onClick: (__VLS_ctx.handleContinue)
};
__VLS_51.slots.default;
var __VLS_51;
/** @type {__VLS_StyleScopedClasses['space-y-6']} */ ;
/** @type {__VLS_StyleScopedClasses['text-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['p-4']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['inline-flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['i-mdi-auto-fix']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-1']} */ ;
/** @type {__VLS_StyleScopedClasses['inline-flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['i-mdi-delete-outline']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-1']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['px-4']} */ ;
/** @type {__VLS_StyleScopedClasses['py-3']} */ ;
/** @type {__VLS_StyleScopedClasses['border-b']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gray-50']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['ml-1']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-red-500']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
/** @type {__VLS_StyleScopedClasses['py-8']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            emit: emit,
            selectedModels: selectedModels,
            tasks: tasks,
            selectedTaskId: selectedTaskId,
            loading: loading,
            isTraining: isTraining,
            availableModels: availableModels,
            columns: columns,
            handleStartAutoTune: handleStartAutoTune,
            handleClearFailedTasks: handleClearFailedTasks,
            handleSelectTask: handleSelectTask,
            handleContinue: handleContinue,
            getStatusColor: getStatusColor,
            formatModelName: formatModelName,
            formatMetric: formatMetric,
            getDisplayMetrics: getDisplayMetrics,
        };
    },
    __typeEmits: {},
    __typeProps: {},
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
    __typeEmits: {},
    __typeProps: {},
});
; /* PartiallyEnd: #4569/main.vue */
