import { ref, computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { message } from "ant-design-vue";
import DefaultLayout from "../../layouts/DefaultLayout.vue";
import PrepareStep from "../../components/ml/prepare/PrepareStep.vue";
import TuningStep from "../../components/ml/tuning/TuningStep.vue";
import PredictionStep from "../../components/ml/prediction/PredictionStep.vue";
import { useWorkItem } from "../../composables";
const route = useRoute();
const router = useRouter();
// Use composable for fetching work item
const workItemId = computed(() => Number(route.params.id));
const { data: workItemData, isLoading: loading, error: fetchError, refetch, } = useWorkItem(workItemId);
// Computed property to safely access work item
const workItem = computed(() => workItemData.value);
const error = computed(() => !!fetchError.value);
// Workflow state
const currentStep = ref(0);
const selectedModel = ref(null);
const selectedParameters = ref({});
const selectedTuningTaskId = ref(null);
// Check if work item has saved prepare data and auto-advance
const checkWorkItemStep = () => {
    if (workItem.value?.datasetId &&
        workItem.value?.featureColumns &&
        workItem.value?.targetColumn) {
        // Skip to tuning step
        currentStep.value = 1;
        message.info("Restored saved dataset configuration");
    }
};
// Watch for work item data and check step
if (workItem.value) {
    checkWorkItemStep();
}
const getStatusColor = (status) => {
    switch (status) {
        case "active":
            return "green";
        case "completed":
            return "blue";
        case "archived":
            return "gray";
        default:
            return "default";
    }
};
const handlePrepareConfirm = () => {
    currentStep.value = 1;
    // Refresh work item to get updated data
    refetch();
};
const handleTuningContinue = (data) => {
    selectedModel.value = data.model;
    selectedParameters.value = data.parameters;
    selectedTuningTaskId.value = data.taskId;
    currentStep.value = 2;
};
const goToPrepareStep = () => {
    currentStep.value = 0;
};
const goToTuningStep = () => {
    currentStep.value = 1;
};
const resetWorkflow = () => {
    currentStep.value = 0;
    selectedModel.value = null;
    selectedParameters.value = {};
    selectedTuningTaskId.value = null;
};
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {[typeof DefaultLayout, typeof DefaultLayout, ]} */ ;
// @ts-ignore
const __VLS_0 = __VLS_asFunctionalComponent(DefaultLayout, new DefaultLayout({}));
const __VLS_1 = __VLS_0({}, ...__VLS_functionalComponentArgsRest(__VLS_0));
var __VLS_3 = {};
__VLS_2.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "max-w-7xl mx-auto px-4 py-8" },
});
const __VLS_4 = {}.ABreadcrumb;
/** @type {[typeof __VLS_components.ABreadcrumb, typeof __VLS_components.aBreadcrumb, typeof __VLS_components.ABreadcrumb, typeof __VLS_components.aBreadcrumb, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
    ...{ class: "mb-6" },
}));
const __VLS_6 = __VLS_5({
    ...{ class: "mb-6" },
}, ...__VLS_functionalComponentArgsRest(__VLS_5));
__VLS_7.slots.default;
const __VLS_8 = {}.ABreadcrumbItem;
/** @type {[typeof __VLS_components.ABreadcrumbItem, typeof __VLS_components.aBreadcrumbItem, typeof __VLS_components.ABreadcrumbItem, typeof __VLS_components.aBreadcrumbItem, ]} */ ;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({}));
const __VLS_10 = __VLS_9({}, ...__VLS_functionalComponentArgsRest(__VLS_9));
__VLS_11.slots.default;
const __VLS_12 = {}.RouterLink;
/** @type {[typeof __VLS_components.RouterLink, typeof __VLS_components.routerLink, typeof __VLS_components.RouterLink, typeof __VLS_components.routerLink, ]} */ ;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
    to: "/",
}));
const __VLS_14 = __VLS_13({
    to: "/",
}, ...__VLS_functionalComponentArgsRest(__VLS_13));
__VLS_15.slots.default;
var __VLS_15;
var __VLS_11;
if (__VLS_ctx.workItem) {
    const __VLS_16 = {}.ABreadcrumbItem;
    /** @type {[typeof __VLS_components.ABreadcrumbItem, typeof __VLS_components.aBreadcrumbItem, typeof __VLS_components.ABreadcrumbItem, typeof __VLS_components.aBreadcrumbItem, ]} */ ;
    // @ts-ignore
    const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({}));
    const __VLS_18 = __VLS_17({}, ...__VLS_functionalComponentArgsRest(__VLS_17));
    __VLS_19.slots.default;
    (__VLS_ctx.workItem.name);
    var __VLS_19;
}
var __VLS_7;
if (__VLS_ctx.loading) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-center py-12" },
    });
    const __VLS_20 = {}.ASpin;
    /** @type {[typeof __VLS_components.ASpin, typeof __VLS_components.aSpin, ]} */ ;
    // @ts-ignore
    const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
        size: "large",
    }));
    const __VLS_22 = __VLS_21({
        size: "large",
    }, ...__VLS_functionalComponentArgsRest(__VLS_21));
}
else if (__VLS_ctx.error) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-center py-12" },
    });
    const __VLS_24 = {}.AResult;
    /** @type {[typeof __VLS_components.AResult, typeof __VLS_components.aResult, typeof __VLS_components.AResult, typeof __VLS_components.aResult, ]} */ ;
    // @ts-ignore
    const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
        status: "404",
        title: "Work Item Not Found",
        subTitle: "The work item you're looking for doesn't exist or you don't have access to it.",
    }));
    const __VLS_26 = __VLS_25({
        status: "404",
        title: "Work Item Not Found",
        subTitle: "The work item you're looking for doesn't exist or you don't have access to it.",
    }, ...__VLS_functionalComponentArgsRest(__VLS_25));
    __VLS_27.slots.default;
    {
        const { extra: __VLS_thisSlot } = __VLS_27.slots;
        const __VLS_28 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({
            ...{ 'onClick': {} },
            type: "primary",
        }));
        const __VLS_30 = __VLS_29({
            ...{ 'onClick': {} },
            type: "primary",
        }, ...__VLS_functionalComponentArgsRest(__VLS_29));
        let __VLS_32;
        let __VLS_33;
        let __VLS_34;
        const __VLS_35 = {
            onClick: (...[$event]) => {
                if (!!(__VLS_ctx.loading))
                    return;
                if (!(__VLS_ctx.error))
                    return;
                __VLS_ctx.router.push('/');
            }
        };
        __VLS_31.slots.default;
        var __VLS_31;
    }
    var __VLS_27;
}
else if (__VLS_ctx.workItem) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "mb-8" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h1, __VLS_intrinsicElements.h1)({
        ...{ class: "text-3xl font-bold mb-2" },
    });
    (__VLS_ctx.workItem.name);
    if (__VLS_ctx.workItem.description) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
            ...{ class: "text-gray-600 mb-3" },
        });
        (__VLS_ctx.workItem.description);
    }
    const __VLS_36 = {}.ATag;
    /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
    // @ts-ignore
    const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
        color: (__VLS_ctx.getStatusColor(__VLS_ctx.workItem.status)),
    }));
    const __VLS_38 = __VLS_37({
        color: (__VLS_ctx.getStatusColor(__VLS_ctx.workItem.status)),
    }, ...__VLS_functionalComponentArgsRest(__VLS_37));
    __VLS_39.slots.default;
    (__VLS_ctx.workItem.status);
    var __VLS_39;
    const __VLS_40 = {}.ACard;
    /** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
    // @ts-ignore
    const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
        ...{ class: "mb-6" },
    }));
    const __VLS_42 = __VLS_41({
        ...{ class: "mb-6" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_41));
    __VLS_43.slots.default;
    const __VLS_44 = {}.ASteps;
    /** @type {[typeof __VLS_components.ASteps, typeof __VLS_components.aSteps, typeof __VLS_components.ASteps, typeof __VLS_components.aSteps, ]} */ ;
    // @ts-ignore
    const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
        current: (__VLS_ctx.currentStep),
        ...{ class: "mb-8" },
    }));
    const __VLS_46 = __VLS_45({
        current: (__VLS_ctx.currentStep),
        ...{ class: "mb-8" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_45));
    __VLS_47.slots.default;
    const __VLS_48 = {}.AStep;
    /** @type {[typeof __VLS_components.AStep, typeof __VLS_components.aStep, ]} */ ;
    // @ts-ignore
    const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
        title: "Prepare",
        description: "Dataset & Column Selection",
    }));
    const __VLS_50 = __VLS_49({
        title: "Prepare",
        description: "Dataset & Column Selection",
    }, ...__VLS_functionalComponentArgsRest(__VLS_49));
    const __VLS_52 = {}.AStep;
    /** @type {[typeof __VLS_components.AStep, typeof __VLS_components.aStep, ]} */ ;
    // @ts-ignore
    const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({
        title: "Tune",
        description: "Model Training & Tuning",
    }));
    const __VLS_54 = __VLS_53({
        title: "Tune",
        description: "Model Training & Tuning",
    }, ...__VLS_functionalComponentArgsRest(__VLS_53));
    const __VLS_56 = {}.AStep;
    /** @type {[typeof __VLS_components.AStep, typeof __VLS_components.aStep, ]} */ ;
    // @ts-ignore
    const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({
        title: "Predict",
        description: "Make Predictions",
    }));
    const __VLS_58 = __VLS_57({
        title: "Predict",
        description: "Make Predictions",
    }, ...__VLS_functionalComponentArgsRest(__VLS_57));
    var __VLS_47;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "mt-6" },
    });
    if (__VLS_ctx.currentStep === 0) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
        /** @type {[typeof PrepareStep, ]} */ ;
        // @ts-ignore
        const __VLS_60 = __VLS_asFunctionalComponent(PrepareStep, new PrepareStep({
            ...{ 'onConfirm': {} },
            workItem: (__VLS_ctx.workItem),
        }));
        const __VLS_61 = __VLS_60({
            ...{ 'onConfirm': {} },
            workItem: (__VLS_ctx.workItem),
        }, ...__VLS_functionalComponentArgsRest(__VLS_60));
        let __VLS_63;
        let __VLS_64;
        let __VLS_65;
        const __VLS_66 = {
            onConfirm: (__VLS_ctx.handlePrepareConfirm)
        };
        var __VLS_62;
    }
    if (__VLS_ctx.currentStep === 1) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
        /** @type {[typeof TuningStep, ]} */ ;
        // @ts-ignore
        const __VLS_67 = __VLS_asFunctionalComponent(TuningStep, new TuningStep({
            ...{ 'onContinue': {} },
            ...{ 'onBack': {} },
            workItemId: (__VLS_ctx.workItem.id),
            datasetId: (__VLS_ctx.workItem.datasetId?.toString() || ''),
            featureColumns: (__VLS_ctx.workItem.featureColumns || []),
            targetColumn: (__VLS_ctx.workItem.targetColumn || ''),
        }));
        const __VLS_68 = __VLS_67({
            ...{ 'onContinue': {} },
            ...{ 'onBack': {} },
            workItemId: (__VLS_ctx.workItem.id),
            datasetId: (__VLS_ctx.workItem.datasetId?.toString() || ''),
            featureColumns: (__VLS_ctx.workItem.featureColumns || []),
            targetColumn: (__VLS_ctx.workItem.targetColumn || ''),
        }, ...__VLS_functionalComponentArgsRest(__VLS_67));
        let __VLS_70;
        let __VLS_71;
        let __VLS_72;
        const __VLS_73 = {
            onContinue: (__VLS_ctx.handleTuningContinue)
        };
        const __VLS_74 = {
            onBack: (__VLS_ctx.goToPrepareStep)
        };
        var __VLS_69;
    }
    if (__VLS_ctx.currentStep === 2) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
        /** @type {[typeof PredictionStep, ]} */ ;
        // @ts-ignore
        const __VLS_75 = __VLS_asFunctionalComponent(PredictionStep, new PredictionStep({
            ...{ 'onBack': {} },
            ...{ 'onReset': {} },
            workItemId: (__VLS_ctx.workItem.id),
            selectedModel: (__VLS_ctx.selectedModel),
            selectedParameters: (__VLS_ctx.selectedParameters),
            taskId: (__VLS_ctx.selectedTuningTaskId),
            featureColumns: (__VLS_ctx.workItem.featureColumns || []),
        }));
        const __VLS_76 = __VLS_75({
            ...{ 'onBack': {} },
            ...{ 'onReset': {} },
            workItemId: (__VLS_ctx.workItem.id),
            selectedModel: (__VLS_ctx.selectedModel),
            selectedParameters: (__VLS_ctx.selectedParameters),
            taskId: (__VLS_ctx.selectedTuningTaskId),
            featureColumns: (__VLS_ctx.workItem.featureColumns || []),
        }, ...__VLS_functionalComponentArgsRest(__VLS_75));
        let __VLS_78;
        let __VLS_79;
        let __VLS_80;
        const __VLS_81 = {
            onBack: (__VLS_ctx.goToTuningStep)
        };
        const __VLS_82 = {
            onReset: (__VLS_ctx.resetWorkflow)
        };
        var __VLS_77;
    }
    var __VLS_43;
}
var __VLS_2;
/** @type {__VLS_StyleScopedClasses['max-w-7xl']} */ ;
/** @type {__VLS_StyleScopedClasses['mx-auto']} */ ;
/** @type {__VLS_StyleScopedClasses['px-4']} */ ;
/** @type {__VLS_StyleScopedClasses['py-8']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
/** @type {__VLS_StyleScopedClasses['py-12']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
/** @type {__VLS_StyleScopedClasses['py-12']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-8']} */ ;
/** @type {__VLS_StyleScopedClasses['text-3xl']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-8']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-6']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            DefaultLayout: DefaultLayout,
            PrepareStep: PrepareStep,
            TuningStep: TuningStep,
            PredictionStep: PredictionStep,
            router: router,
            loading: loading,
            workItem: workItem,
            error: error,
            currentStep: currentStep,
            selectedModel: selectedModel,
            selectedParameters: selectedParameters,
            selectedTuningTaskId: selectedTuningTaskId,
            getStatusColor: getStatusColor,
            handlePrepareConfirm: handlePrepareConfirm,
            handleTuningContinue: handleTuningContinue,
            goToPrepareStep: goToPrepareStep,
            goToTuningStep: goToTuningStep,
            resetWorkflow: resetWorkflow,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
