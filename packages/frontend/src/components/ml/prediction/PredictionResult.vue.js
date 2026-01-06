import { ref, computed, onMounted, onUnmounted } from 'vue';
import { message } from 'ant-design-vue';
const props = defineProps();
// State
const task = ref(null);
const downloading = ref(false);
const loading = ref(false);
// Polling interval
let pollInterval = null;
// Computed
const statusMessage = computed(() => {
    if (!task.value)
        return '';
    switch (task.value.status) {
        case 'pending':
            return 'Prediction task queued';
        case 'running':
            return 'Generating predictions...';
        case 'completed':
            return 'Prediction completed successfully!';
        case 'failed':
            return `Prediction failed: ${task.value.error || 'Unknown error'}`;
        default:
            return '';
    }
});
const statusType = computed(() => {
    if (!task.value)
        return 'info';
    switch (task.value.status) {
        case 'completed':
            return 'success';
        case 'failed':
            return 'error';
        case 'running':
            return 'info';
        default:
            return 'info';
    }
});
const resultColumns = computed(() => {
    if (!task.value?.result?.predictions || task.value.result.predictions.length === 0) {
        return [];
    }
    const firstRow = task.value.result.predictions[0];
    const cols = Object.keys(firstRow)
        .filter(key => key !== 'prediction')
        .map(key => ({
        title: key,
        dataIndex: key,
        key,
    }));
    cols.push({
        title: 'Prediction',
        dataIndex: 'prediction',
        key: 'prediction',
    });
    return cols;
});
const formattedResults = computed(() => {
    if (!task.value?.result?.predictions)
        return [];
    return task.value.result.predictions.map((pred, index) => ({
        ...pred,
        key: index,
    }));
});
const avgPrediction = computed(() => {
    if (!task.value?.result?.predictions || task.value.result.predictions.length === 0) {
        return '-';
    }
    const predictions = task.value.result.predictions.map((p) => p.prediction);
    const sum = predictions.reduce((acc, val) => acc + val, 0);
    const avg = sum / predictions.length;
    return avg.toFixed(4);
});
/**
 * Fetch task status
 */
const fetchTaskStatus = async () => {
    loading.value = true;
    try {
        const response = await TaskService.fetchStatus(props.taskId);
        task.value = response.task;
    }
    catch (error) {
        console.error('Failed to fetch task:', error);
    }
    finally {
        loading.value = false;
    }
};
/**
 * Start polling for task updates
 */
const startPolling = () => {
    if (pollInterval)
        return;
    pollInterval = window.setInterval(() => {
        if (task.value && (task.value.status === 'pending' || task.value.status === 'running')) {
            fetchTaskStatus();
        }
        else {
            stopPolling();
        }
    }, 2000);
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
 * Download result file
 */
const handleDownload = async () => {
    if (!task.value?.result?.outputFile)
        return;
    downloading.value = true;
    try {
        // Create download link
        const link = document.createElement('a');
        link.href = `/api/download/${task.value.id}`;
        link.download = task.value.result.outputFile;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        message.success('Download started');
    }
    catch (error) {
        console.error('Download failed:', error);
        message.error(error.message || 'Failed to download file');
    }
    finally {
        downloading.value = false;
    }
};
// Lifecycle
onMounted(async () => {
    await fetchTaskStatus();
    if (task.value && (task.value.status === 'pending' || task.value.status === 'running')) {
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
    ...{ class: "space-y-4" },
});
if (__VLS_ctx.task) {
    const __VLS_0 = {}.AAlert;
    /** @type {[typeof __VLS_components.AAlert, typeof __VLS_components.aAlert, ]} */ ;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
        message: (__VLS_ctx.statusMessage),
        type: (__VLS_ctx.statusType),
        showIcon: true,
        closable: true,
    }));
    const __VLS_2 = __VLS_1({
        message: (__VLS_ctx.statusMessage),
        type: (__VLS_ctx.statusType),
        showIcon: true,
        closable: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
}
if (__VLS_ctx.task && (__VLS_ctx.task.status === 'pending' || __VLS_ctx.task.status === 'running')) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-center py-8" },
    });
    const __VLS_4 = {}.ASpin;
    /** @type {[typeof __VLS_components.ASpin, typeof __VLS_components.aSpin, ]} */ ;
    // @ts-ignore
    const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
        size: "large",
    }));
    const __VLS_6 = __VLS_5({
        size: "large",
    }, ...__VLS_functionalComponentArgsRest(__VLS_5));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "mt-4 text-gray-600" },
    });
}
else if (__VLS_ctx.task && __VLS_ctx.task.status === 'completed') {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    if (__VLS_ctx.task.result?.outputFile) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "mb-4" },
        });
        const __VLS_8 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
            ...{ 'onClick': {} },
            type: "primary",
            ...{ class: "inline-flex items-center" },
            loading: (__VLS_ctx.downloading),
        }));
        const __VLS_10 = __VLS_9({
            ...{ 'onClick': {} },
            type: "primary",
            ...{ class: "inline-flex items-center" },
            loading: (__VLS_ctx.downloading),
        }, ...__VLS_functionalComponentArgsRest(__VLS_9));
        let __VLS_12;
        let __VLS_13;
        let __VLS_14;
        const __VLS_15 = {
            onClick: (__VLS_ctx.handleDownload)
        };
        __VLS_11.slots.default;
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "i-mdi-download mr-2" },
        });
        var __VLS_11;
    }
    if (__VLS_ctx.task.result?.predictions) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "bg-white rounded-lg border p-4" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({
            ...{ class: "text-md font-medium mb-3" },
        });
        const __VLS_16 = {}.ATable;
        /** @type {[typeof __VLS_components.ATable, typeof __VLS_components.aTable, typeof __VLS_components.ATable, typeof __VLS_components.aTable, ]} */ ;
        // @ts-ignore
        const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
            columns: (__VLS_ctx.resultColumns),
            dataSource: (__VLS_ctx.formattedResults),
            pagination: (false),
            bordered: true,
            size: "small",
        }));
        const __VLS_18 = __VLS_17({
            columns: (__VLS_ctx.resultColumns),
            dataSource: (__VLS_ctx.formattedResults),
            pagination: (false),
            bordered: true,
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_17));
        __VLS_19.slots.default;
        {
            const { bodyCell: __VLS_thisSlot } = __VLS_19.slots;
            const [{ column, record }] = __VLS_getSlotParams(__VLS_thisSlot);
            if (column.key === 'prediction') {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "font-semibold text-blue-600" },
                });
                (record.prediction);
            }
        }
        var __VLS_19;
    }
    if (__VLS_ctx.task.result?.predictions) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "bg-gray-50 rounded-lg p-4 mt-4" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({
            ...{ class: "text-md font-medium mb-2" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "grid grid-cols-2 gap-4 text-sm" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "text-gray-600" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "ml-2 font-medium" },
        });
        (__VLS_ctx.task.result.predictions.length);
        if (__VLS_ctx.task.result.predictions.length > 0) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "text-gray-600" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "ml-2 font-medium" },
            });
            (__VLS_ctx.avgPrediction);
        }
    }
}
else if (__VLS_ctx.task && __VLS_ctx.task.status === 'failed') {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-center py-8" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "i-mdi-alert-circle text-6xl text-red-500 inline-block mb-4" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
        ...{ class: "text-xl font-semibold text-red-600 mb-2" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "text-gray-600" },
    });
    (__VLS_ctx.task.error || 'An unknown error occurred');
}
/** @type {__VLS_StyleScopedClasses['space-y-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
/** @type {__VLS_StyleScopedClasses['py-8']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['inline-flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['i-mdi-download']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-2']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['p-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-md']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-blue-600']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gray-50']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['p-4']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-md']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['grid']} */ ;
/** @type {__VLS_StyleScopedClasses['grid-cols-2']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['ml-2']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['ml-2']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
/** @type {__VLS_StyleScopedClasses['py-8']} */ ;
/** @type {__VLS_StyleScopedClasses['i-mdi-alert-circle']} */ ;
/** @type {__VLS_StyleScopedClasses['text-6xl']} */ ;
/** @type {__VLS_StyleScopedClasses['text-red-500']} */ ;
/** @type {__VLS_StyleScopedClasses['inline-block']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-red-600']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            task: task,
            downloading: downloading,
            statusMessage: statusMessage,
            statusType: statusType,
            resultColumns: resultColumns,
            formattedResults: formattedResults,
            avgPrediction: avgPrediction,
            handleDownload: handleDownload,
        };
    },
    __typeProps: {},
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
    __typeProps: {},
});
; /* PartiallyEnd: #4569/main.vue */
