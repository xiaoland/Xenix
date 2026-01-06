import { ref, computed } from 'vue';
import { message } from 'ant-design-vue';
import DatasetSelector from '../../dataset/DatasetSelector.vue';
import ColumnSelector from './ColumnSelector.vue';
import { useUpdateWorkItem } from '../../../composables';
const props = defineProps();
const emit = defineEmits();
const selectedDatasetId = ref(props.workItem.datasetId);
const selectedDatasetName = ref('');
const datasetColumns = ref([]);
const featureColumns = ref(props.workItem.featureColumns || []);
const targetColumn = ref(props.workItem.targetColumn);
// Use composable for updating work item
const { mutate: updateWorkItem, isPending: saving } = useUpdateWorkItem();
const canConfirm = computed(() => {
    return (selectedDatasetId.value &&
        featureColumns.value.length > 0 &&
        targetColumn.value);
});
const handleDatasetSelect = async (dataset) => {
    selectedDatasetId.value = dataset.id;
    selectedDatasetName.value = dataset.name;
    datasetColumns.value = dataset.columns;
    // Reset column selections when changing dataset
    featureColumns.value = [];
    targetColumn.value = undefined;
};
const changeDataset = () => {
    selectedDatasetId.value = undefined;
    selectedDatasetName.value = '';
    datasetColumns.value = [];
    featureColumns.value = [];
    targetColumn.value = undefined;
};
const handleConfirm = () => {
    if (!canConfirm.value)
        return;
    updateWorkItem({
        id: props.workItem.id,
        updates: {
            datasetId: selectedDatasetId.value,
            featureColumns: featureColumns.value,
            targetColumn: targetColumn.value,
        },
    }, {
        onSuccess: () => {
            message.success('Dataset configuration saved successfully');
            emit('confirm');
        },
        onError: (error) => {
            console.error('Failed to save configuration:', error);
            message.error('Failed to save configuration');
        }
    });
};
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "space-y-6" },
});
const __VLS_0 = {}.AAlert;
/** @type {[typeof __VLS_components.AAlert, typeof __VLS_components.aAlert, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    message: "Prepare Your Data",
    description: "Select a dataset and choose the feature columns and target column for your machine learning model.",
    type: "info",
    showIcon: true,
    ...{ class: "mb-4" },
}));
const __VLS_2 = __VLS_1({
    message: "Prepare Your Data",
    description: "Select a dataset and choose the feature columns and target column for your machine learning model.",
    type: "info",
    showIcon: true,
    ...{ class: "mb-4" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
if (!__VLS_ctx.selectedDatasetId) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
        ...{ class: "text-lg font-semibold mb-4" },
    });
    /** @type {[typeof DatasetSelector, ]} */ ;
    // @ts-ignore
    const __VLS_4 = __VLS_asFunctionalComponent(DatasetSelector, new DatasetSelector({
        ...{ 'onSelect': {} },
        projectId: (__VLS_ctx.workItem.projectId),
    }));
    const __VLS_5 = __VLS_4({
        ...{ 'onSelect': {} },
        projectId: (__VLS_ctx.workItem.projectId),
    }, ...__VLS_functionalComponentArgsRest(__VLS_4));
    let __VLS_7;
    let __VLS_8;
    let __VLS_9;
    const __VLS_10 = {
        onSelect: (__VLS_ctx.handleDatasetSelect)
    };
    var __VLS_6;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "mt-4" },
    });
    const __VLS_11 = {}.RouterLink;
    /** @type {[typeof __VLS_components.RouterLink, typeof __VLS_components.routerLink, typeof __VLS_components.RouterLink, typeof __VLS_components.routerLink, ]} */ ;
    // @ts-ignore
    const __VLS_12 = __VLS_asFunctionalComponent(__VLS_11, new __VLS_11({
        to: (`/projects/${__VLS_ctx.workItem.projectId}/datasets`),
    }));
    const __VLS_13 = __VLS_12({
        to: (`/projects/${__VLS_ctx.workItem.projectId}/datasets`),
    }, ...__VLS_functionalComponentArgsRest(__VLS_12));
    __VLS_14.slots.default;
    const __VLS_15 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_16 = __VLS_asFunctionalComponent(__VLS_15, new __VLS_15({
        type: "default",
        ...{ class: "inline-flex items-center" },
    }));
    const __VLS_17 = __VLS_16({
        type: "default",
        ...{ class: "inline-flex items-center" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_16));
    __VLS_18.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "i-mdi-cloud-upload mr-2" },
    });
    var __VLS_18;
    var __VLS_14;
}
else {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
        ...{ class: "text-lg font-semibold mb-4" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "bg-gray-50 p-4 rounded mb-4" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex items-center justify-between" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "font-medium" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "ml-2" },
    });
    (__VLS_ctx.selectedDatasetName);
    const __VLS_19 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_20 = __VLS_asFunctionalComponent(__VLS_19, new __VLS_19({
        ...{ 'onClick': {} },
        size: "small",
    }));
    const __VLS_21 = __VLS_20({
        ...{ 'onClick': {} },
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_20));
    let __VLS_23;
    let __VLS_24;
    let __VLS_25;
    const __VLS_26 = {
        onClick: (__VLS_ctx.changeDataset)
    };
    __VLS_22.slots.default;
    var __VLS_22;
    /** @type {[typeof ColumnSelector, ]} */ ;
    // @ts-ignore
    const __VLS_27 = __VLS_asFunctionalComponent(ColumnSelector, new ColumnSelector({
        ...{ 'onUpdate:featureColumns': {} },
        ...{ 'onUpdate:targetColumn': {} },
        columns: (__VLS_ctx.datasetColumns),
        featureColumns: (__VLS_ctx.featureColumns),
        targetColumn: (__VLS_ctx.targetColumn),
    }));
    const __VLS_28 = __VLS_27({
        ...{ 'onUpdate:featureColumns': {} },
        ...{ 'onUpdate:targetColumn': {} },
        columns: (__VLS_ctx.datasetColumns),
        featureColumns: (__VLS_ctx.featureColumns),
        targetColumn: (__VLS_ctx.targetColumn),
    }, ...__VLS_functionalComponentArgsRest(__VLS_27));
    let __VLS_30;
    let __VLS_31;
    let __VLS_32;
    const __VLS_33 = {
        'onUpdate:featureColumns': (...[$event]) => {
            if (!!(!__VLS_ctx.selectedDatasetId))
                return;
            __VLS_ctx.featureColumns = $event;
        }
    };
    const __VLS_34 = {
        'onUpdate:targetColumn': (...[$event]) => {
            if (!!(!__VLS_ctx.selectedDatasetId))
                return;
            __VLS_ctx.targetColumn = $event;
        }
    };
    var __VLS_29;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex justify-between mt-6" },
    });
    const __VLS_35 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_36 = __VLS_asFunctionalComponent(__VLS_35, new __VLS_35({
        ...{ 'onClick': {} },
    }));
    const __VLS_37 = __VLS_36({
        ...{ 'onClick': {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_36));
    let __VLS_39;
    let __VLS_40;
    let __VLS_41;
    const __VLS_42 = {
        onClick: (__VLS_ctx.changeDataset)
    };
    __VLS_38.slots.default;
    var __VLS_38;
    const __VLS_43 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_44 = __VLS_asFunctionalComponent(__VLS_43, new __VLS_43({
        ...{ 'onClick': {} },
        type: "primary",
        disabled: (!__VLS_ctx.canConfirm),
        loading: (__VLS_ctx.saving),
    }));
    const __VLS_45 = __VLS_44({
        ...{ 'onClick': {} },
        type: "primary",
        disabled: (!__VLS_ctx.canConfirm),
        loading: (__VLS_ctx.saving),
    }, ...__VLS_functionalComponentArgsRest(__VLS_44));
    let __VLS_47;
    let __VLS_48;
    let __VLS_49;
    const __VLS_50 = {
        onClick: (__VLS_ctx.handleConfirm)
    };
    __VLS_46.slots.default;
    var __VLS_46;
}
/** @type {__VLS_StyleScopedClasses['space-y-6']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-4']} */ ;
/** @type {__VLS_StyleScopedClasses['inline-flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['i-mdi-cloud-upload']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gray-50']} */ ;
/** @type {__VLS_StyleScopedClasses['p-4']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['ml-2']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-6']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            DatasetSelector: DatasetSelector,
            ColumnSelector: ColumnSelector,
            selectedDatasetId: selectedDatasetId,
            selectedDatasetName: selectedDatasetName,
            datasetColumns: datasetColumns,
            featureColumns: featureColumns,
            targetColumn: targetColumn,
            saving: saving,
            canConfirm: canConfirm,
            handleDatasetSelect: handleDatasetSelect,
            changeDataset: changeDataset,
            handleConfirm: handleConfirm,
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
