import { ref, computed } from 'vue';
import { message } from 'ant-design-vue';
import { AVAILABLE_MODELS } from '../../../constants/models';
import PredictionResult from './PredictionResult.vue';
const props = defineProps();
const emit = defineEmits();
// State
const predictionMode = ref('file');
const fileList = ref([]);
const inputData = ref([]);
const isPredicting = ref(false);
const predictionTaskId = ref(null);
// Computed
const inputColumns = computed(() => {
    const cols = props.featureColumns.map((col) => ({
        title: col,
        dataIndex: col,
        key: col,
        width: 150,
    }));
    cols.push({
        title: 'Action',
        key: 'action',
        width: 100,
    });
    return cols;
});
/**
 * Format model name for display
 */
const formatModelName = (modelValue) => {
    const model = AVAILABLE_MODELS.find(m => m.value === modelValue);
    return model ? model.label : modelValue;
};
/**
 * Add a new row to inline input
 */
const addRow = () => {
    const newRow = { key: Date.now() };
    props.featureColumns.forEach((col) => {
        newRow[col] = null;
    });
    inputData.value.push(newRow);
};
/**
 * Remove a row from inline input
 */
const removeRow = (index) => {
    inputData.value.splice(index, 1);
};
/**
 * Before upload handler
 */
const beforeUpload = (file) => {
    const isExcelOrCsv = file.type === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' ||
        file.type === 'application/vnd.ms-excel' ||
        file.type === 'text/csv';
    if (!isExcelOrCsv) {
        message.error('You can only upload Excel or CSV files!');
        return false;
    }
    const isLt10M = file.size / 1024 / 1024 < 10;
    if (!isLt10M) {
        message.error('File must be smaller than 10MB!');
        return false;
    }
    return false; // Prevent auto upload
};
/**
 * Start prediction from uploaded file
 */
const startPredictionFromFile = async () => {
    if (fileList.value.length === 0 || !props.selectedModel || !props.taskId) {
        return;
    }
    isPredicting.value = true;
    try {
        const file = fileList.value[0].originFileObj || fileList.value[0];
        const response = await PredictionService.start({
            file,
            model: props.selectedModel,
            tuningTaskId: props.taskId,
            workItemId: props.workItemId,
        });
        message.success('Prediction started successfully');
        predictionTaskId.value = response.taskId;
        fileList.value = [];
    }
    catch (error) {
        console.error('Prediction failed:', error);
        message.error(error.message || 'Failed to start prediction');
    }
    finally {
        isPredicting.value = false;
    }
};
/**
 * Predict with inline data
 */
const predictInline = async () => {
    if (inputData.value.length === 0 || !props.selectedModel || !props.taskId) {
        return;
    }
    // Validate that all fields are filled
    const hasEmptyFields = inputData.value.some(row => props.featureColumns.some(col => row[col] === null || row[col] === undefined));
    if (hasEmptyFields) {
        message.error('Please fill in all fields');
        return;
    }
    isPredicting.value = true;
    try {
        // Remove the 'key' field from data
        const cleanData = inputData.value.map(row => {
            const { key, ...rest } = row;
            return rest;
        });
        const response = await PredictionService.predictInline({
            predictionData: cleanData,
            model: props.selectedModel,
            tuningTaskId: props.taskId,
            workItemId: props.workItemId,
        });
        message.success('Prediction completed successfully');
        predictionTaskId.value = response.taskId;
    }
    catch (error) {
        console.error('Prediction failed:', error);
        message.error(error.message || 'Failed to predict');
    }
    finally {
        isPredicting.value = false;
    }
};
/**
 * Reset workflow
 */
const handleReset = () => {
    emit('reset');
};
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
if (__VLS_ctx.selectedModel) {
    const __VLS_0 = {}.AAlert;
    /** @type {[typeof __VLS_components.AAlert, typeof __VLS_components.aAlert, ]} */ ;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
        message: (`Using trained model: ${__VLS_ctx.formatModelName(__VLS_ctx.selectedModel)}`),
        type: "success",
        showIcon: true,
        ...{ class: "mb-4" },
    }));
    const __VLS_2 = __VLS_1({
        message: (`Using trained model: ${__VLS_ctx.formatModelName(__VLS_ctx.selectedModel)}`),
        type: "success",
        showIcon: true,
        ...{ class: "mb-4" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "bg-white rounded-lg border p-4" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
    ...{ class: "block text-sm font-medium text-gray-700 mb-2" },
});
const __VLS_4 = {}.ARadioGroup;
/** @type {[typeof __VLS_components.ARadioGroup, typeof __VLS_components.aRadioGroup, typeof __VLS_components.ARadioGroup, typeof __VLS_components.aRadioGroup, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
    value: (__VLS_ctx.predictionMode),
    buttonStyle: "solid",
}));
const __VLS_6 = __VLS_5({
    value: (__VLS_ctx.predictionMode),
    buttonStyle: "solid",
}, ...__VLS_functionalComponentArgsRest(__VLS_5));
__VLS_7.slots.default;
const __VLS_8 = {}.ARadioButton;
/** @type {[typeof __VLS_components.ARadioButton, typeof __VLS_components.aRadioButton, typeof __VLS_components.ARadioButton, typeof __VLS_components.aRadioButton, ]} */ ;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
    value: "file",
}));
const __VLS_10 = __VLS_9({
    value: "file",
}, ...__VLS_functionalComponentArgsRest(__VLS_9));
__VLS_11.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "inline-flex items-center" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "i-mdi-file-upload mr-2" },
});
var __VLS_11;
const __VLS_12 = {}.ARadioButton;
/** @type {[typeof __VLS_components.ARadioButton, typeof __VLS_components.aRadioButton, typeof __VLS_components.ARadioButton, typeof __VLS_components.aRadioButton, ]} */ ;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
    value: "inline",
}));
const __VLS_14 = __VLS_13({
    value: "inline",
}, ...__VLS_functionalComponentArgsRest(__VLS_13));
__VLS_15.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "inline-flex items-center" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "i-mdi-table-edit mr-2" },
});
var __VLS_15;
var __VLS_7;
if (__VLS_ctx.predictionMode === 'file') {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "bg-white rounded-lg border p-4" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
        ...{ class: "text-lg font-medium mb-3" },
    });
    const __VLS_16 = {}.AUploadDragger;
    /** @type {[typeof __VLS_components.AUploadDragger, typeof __VLS_components.aUploadDragger, typeof __VLS_components.AUploadDragger, typeof __VLS_components.aUploadDragger, ]} */ ;
    // @ts-ignore
    const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
        fileList: (__VLS_ctx.fileList),
        name: "file",
        beforeUpload: (__VLS_ctx.beforeUpload),
        maxCount: (1),
        accept: ".xlsx,.xls,.csv",
    }));
    const __VLS_18 = __VLS_17({
        fileList: (__VLS_ctx.fileList),
        name: "file",
        beforeUpload: (__VLS_ctx.beforeUpload),
        maxCount: (1),
        accept: ".xlsx,.xls,.csv",
    }, ...__VLS_functionalComponentArgsRest(__VLS_17));
    __VLS_19.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "ant-upload-drag-icon" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "i-mdi-file-table text-6xl text-green-500 inline-block" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "ant-upload-text" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "ant-upload-hint" },
    });
    var __VLS_19;
    const __VLS_20 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
        ...{ 'onClick': {} },
        ...{ class: "mt-4 inline-flex items-center justify-center" },
        type: "primary",
        size: "large",
        block: true,
        loading: (__VLS_ctx.isPredicting),
        disabled: (__VLS_ctx.fileList.length === 0),
    }));
    const __VLS_22 = __VLS_21({
        ...{ 'onClick': {} },
        ...{ class: "mt-4 inline-flex items-center justify-center" },
        type: "primary",
        size: "large",
        block: true,
        loading: (__VLS_ctx.isPredicting),
        disabled: (__VLS_ctx.fileList.length === 0),
    }, ...__VLS_functionalComponentArgsRest(__VLS_21));
    let __VLS_24;
    let __VLS_25;
    let __VLS_26;
    const __VLS_27 = {
        onClick: (__VLS_ctx.startPredictionFromFile)
    };
    __VLS_23.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span)({
        ...{ class: "i-mdi-chart-line mr-2" },
    });
    var __VLS_23;
}
else if (__VLS_ctx.predictionMode === 'inline') {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "bg-white rounded-lg border p-4" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex items-center justify-between mb-3" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
        ...{ class: "text-lg font-medium" },
    });
    const __VLS_28 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({
        ...{ 'onClick': {} },
        type: "primary",
        ...{ class: "inline-flex items-center" },
    }));
    const __VLS_30 = __VLS_29({
        ...{ 'onClick': {} },
        type: "primary",
        ...{ class: "inline-flex items-center" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_29));
    let __VLS_32;
    let __VLS_33;
    let __VLS_34;
    const __VLS_35 = {
        onClick: (__VLS_ctx.addRow)
    };
    __VLS_31.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span)({
        ...{ class: "i-mdi-plus mr-1" },
    });
    var __VLS_31;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "text-sm text-gray-600 mb-4" },
    });
    if (__VLS_ctx.inputData.length > 0) {
        const __VLS_36 = {}.ATable;
        /** @type {[typeof __VLS_components.ATable, typeof __VLS_components.aTable, typeof __VLS_components.ATable, typeof __VLS_components.aTable, ]} */ ;
        // @ts-ignore
        const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
            columns: (__VLS_ctx.inputColumns),
            dataSource: (__VLS_ctx.inputData),
            pagination: (false),
            bordered: true,
            size: "small",
            ...{ class: "mb-4" },
        }));
        const __VLS_38 = __VLS_37({
            columns: (__VLS_ctx.inputColumns),
            dataSource: (__VLS_ctx.inputData),
            pagination: (false),
            bordered: true,
            size: "small",
            ...{ class: "mb-4" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_37));
        __VLS_39.slots.default;
        {
            const { bodyCell: __VLS_thisSlot } = __VLS_39.slots;
            const [{ column, record, index }] = __VLS_getSlotParams(__VLS_thisSlot);
            if (column.key === 'action') {
                const __VLS_40 = {}.AButton;
                /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
                // @ts-ignore
                const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
                    ...{ 'onClick': {} },
                    type: "link",
                    danger: true,
                    size: "small",
                    ...{ class: "inline-flex items-center" },
                }));
                const __VLS_42 = __VLS_41({
                    ...{ 'onClick': {} },
                    type: "link",
                    danger: true,
                    size: "small",
                    ...{ class: "inline-flex items-center" },
                }, ...__VLS_functionalComponentArgsRest(__VLS_41));
                let __VLS_44;
                let __VLS_45;
                let __VLS_46;
                const __VLS_47 = {
                    onClick: (...[$event]) => {
                        if (!!(__VLS_ctx.predictionMode === 'file'))
                            return;
                        if (!(__VLS_ctx.predictionMode === 'inline'))
                            return;
                        if (!(__VLS_ctx.inputData.length > 0))
                            return;
                        if (!(column.key === 'action'))
                            return;
                        __VLS_ctx.removeRow(index);
                    }
                };
                __VLS_43.slots.default;
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span)({
                    ...{ class: "i-mdi-delete mr-1" },
                });
                var __VLS_43;
            }
            else if (column.key) {
                const __VLS_48 = {}.AInputNumber;
                /** @type {[typeof __VLS_components.AInputNumber, typeof __VLS_components.aInputNumber, ]} */ ;
                // @ts-ignore
                const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
                    value: (record[column.key]),
                    placeholder: (`Enter ${column.title}`),
                    ...{ style: {} },
                    precision: (4),
                }));
                const __VLS_50 = __VLS_49({
                    value: (record[column.key]),
                    placeholder: (`Enter ${column.title}`),
                    ...{ style: {} },
                    precision: (4),
                }, ...__VLS_functionalComponentArgsRest(__VLS_49));
            }
        }
        var __VLS_39;
    }
    else {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "text-center py-8 text-gray-500" },
        });
    }
    const __VLS_52 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({
        ...{ 'onClick': {} },
        type: "primary",
        size: "large",
        block: true,
        loading: (__VLS_ctx.isPredicting),
        disabled: (__VLS_ctx.inputData.length === 0),
        ...{ class: "inline-flex items-center justify-center" },
    }));
    const __VLS_54 = __VLS_53({
        ...{ 'onClick': {} },
        type: "primary",
        size: "large",
        block: true,
        loading: (__VLS_ctx.isPredicting),
        disabled: (__VLS_ctx.inputData.length === 0),
        ...{ class: "inline-flex items-center justify-center" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_53));
    let __VLS_56;
    let __VLS_57;
    let __VLS_58;
    const __VLS_59 = {
        onClick: (__VLS_ctx.predictInline)
    };
    __VLS_55.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span)({
        ...{ class: "i-mdi-chart-line mr-2" },
    });
    var __VLS_55;
}
if (__VLS_ctx.predictionTaskId) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "bg-white rounded-lg border p-4" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
        ...{ class: "text-lg font-medium mb-3" },
    });
    /** @type {[typeof PredictionResult, ]} */ ;
    // @ts-ignore
    const __VLS_60 = __VLS_asFunctionalComponent(PredictionResult, new PredictionResult({
        taskId: (__VLS_ctx.predictionTaskId),
        workItemId: (__VLS_ctx.workItemId),
    }));
    const __VLS_61 = __VLS_60({
        taskId: (__VLS_ctx.predictionTaskId),
        workItemId: (__VLS_ctx.workItemId),
    }, ...__VLS_functionalComponentArgsRest(__VLS_60));
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex justify-between" },
});
const __VLS_63 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_64 = __VLS_asFunctionalComponent(__VLS_63, new __VLS_63({
    ...{ 'onClick': {} },
}));
const __VLS_65 = __VLS_64({
    ...{ 'onClick': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_64));
let __VLS_67;
let __VLS_68;
let __VLS_69;
const __VLS_70 = {
    onClick: (...[$event]) => {
        __VLS_ctx.emit('back');
    }
};
__VLS_66.slots.default;
var __VLS_66;
const __VLS_71 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_72 = __VLS_asFunctionalComponent(__VLS_71, new __VLS_71({
    ...{ 'onClick': {} },
}));
const __VLS_73 = __VLS_72({
    ...{ 'onClick': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_72));
let __VLS_75;
let __VLS_76;
let __VLS_77;
const __VLS_78 = {
    onClick: (__VLS_ctx.handleReset)
};
__VLS_74.slots.default;
var __VLS_74;
/** @type {__VLS_StyleScopedClasses['space-y-6']} */ ;
/** @type {__VLS_StyleScopedClasses['text-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['p-4']} */ ;
/** @type {__VLS_StyleScopedClasses['block']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['inline-flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['i-mdi-file-upload']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-2']} */ ;
/** @type {__VLS_StyleScopedClasses['inline-flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['i-mdi-table-edit']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-2']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['p-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-upload-drag-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['i-mdi-file-table']} */ ;
/** @type {__VLS_StyleScopedClasses['text-6xl']} */ ;
/** @type {__VLS_StyleScopedClasses['text-green-500']} */ ;
/** @type {__VLS_StyleScopedClasses['inline-block']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-upload-text']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-upload-hint']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-4']} */ ;
/** @type {__VLS_StyleScopedClasses['inline-flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['i-mdi-chart-line']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-2']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['p-4']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['inline-flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['i-mdi-plus']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['inline-flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['i-mdi-delete']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
/** @type {__VLS_StyleScopedClasses['py-8']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['inline-flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['i-mdi-chart-line']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-2']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['p-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            PredictionResult: PredictionResult,
            emit: emit,
            predictionMode: predictionMode,
            fileList: fileList,
            inputData: inputData,
            isPredicting: isPredicting,
            predictionTaskId: predictionTaskId,
            inputColumns: inputColumns,
            formatModelName: formatModelName,
            addRow: addRow,
            removeRow: removeRow,
            beforeUpload: beforeUpload,
            startPredictionFromFile: startPredictionFromFile,
            predictInline: predictInline,
            handleReset: handleReset,
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
