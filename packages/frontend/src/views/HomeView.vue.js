/// <reference types="../../node_modules/.vue-global-types/vue_3.5_0_0_0.d.ts" />
import { ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import { message } from 'ant-design-vue';
import DefaultLayout from '../layouts/DefaultLayout.vue';
import ProjectCard from '../components/project/ProjectCard.vue';
import ProjectFormModal from '../components/project/ProjectFormModal.vue';
import { useProjects, useCreateProject, useUpdateProject, useDeleteProject } from '../composables';
const router = useRouter();
// Use composables for data fetching
const { data: projectsData, isLoading, error } = useProjects();
const { mutate: createProject, isPending: isCreating } = useCreateProject();
const { mutate: updateProject, isPending: isUpdating } = useUpdateProject();
const { mutate: deleteProject, isPending: isDeleting } = useDeleteProject();
// Computed property to safely access projects array
const projects = computed(() => projectsData.value || []);
const showCreateModal = ref(false);
const showEditModal = ref(false);
const editingProject = ref({});
const handleCreate = (values) => {
    createProject(values, {
        onSuccess: () => {
            message.success('Project created successfully');
            showCreateModal.value = false;
        },
        onError: (error) => {
            console.error('Failed to create project:', error);
            message.error('Failed to create project');
        }
    });
};
const handleEdit = (project) => {
    editingProject.value = { ...project };
    showEditModal.value = true;
};
const handleUpdate = (values) => {
    if (!editingProject.value.id)
        return;
    updateProject({ id: editingProject.value.id, updates: values }, {
        onSuccess: () => {
            message.success('Project updated successfully');
            showEditModal.value = false;
        },
        onError: (error) => {
            console.error('Failed to update project:', error);
            message.error('Failed to update project');
        }
    });
};
const handleDelete = (projectId) => {
    deleteProject(projectId, {
        onSuccess: () => {
            message.success('Project deleted successfully');
        },
        onError: (error) => {
            console.error('Failed to delete project:', error);
            message.error('Failed to delete project');
        }
    });
};
const handleManageDatasets = (projectId) => {
    router.push(`/projects/${projectId}/datasets`);
};
const handleAddWorkItem = (projectId) => {
    router.push(`/work-items/new?projectId=${projectId}`);
};
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
// CSS variable injection 
// CSS variable injection end 
/** @type {[typeof DefaultLayout, typeof DefaultLayout, ]} */ ;
// @ts-ignore
const __VLS_0 = __VLS_asFunctionalComponent(DefaultLayout, new DefaultLayout({}));
const __VLS_1 = __VLS_0({}, ...__VLS_functionalComponentArgsRest(__VLS_0));
var __VLS_3 = {};
__VLS_2.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "max-w-7xl mx-auto px-4 sm:px-6 lg:px-8" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-center mb-8" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h1, __VLS_intrinsicElements.h1)({
    ...{ class: "text-4xl font-bold text-gray-900 mb-2" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "text-lg text-gray-600" },
});
const __VLS_4 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
    ...{ class: "mb-6" },
}));
const __VLS_6 = __VLS_5({
    ...{ class: "mb-6" },
}, ...__VLS_functionalComponentArgsRest(__VLS_5));
__VLS_7.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex justify-between items-center mb-4" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({
    ...{ class: "text-2xl font-semibold" },
});
const __VLS_8 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
    ...{ 'onClick': {} },
    type: "primary",
    ...{ class: "inline-flex items-center" },
}));
const __VLS_10 = __VLS_9({
    ...{ 'onClick': {} },
    type: "primary",
    ...{ class: "inline-flex items-center" },
}, ...__VLS_functionalComponentArgsRest(__VLS_9));
let __VLS_12;
let __VLS_13;
let __VLS_14;
const __VLS_15 = {
    onClick: (...[$event]) => {
        __VLS_ctx.showCreateModal = true;
    }
};
__VLS_11.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.span)({
    ...{ class: "i-mdi-plus mr-1" },
});
var __VLS_11;
const __VLS_16 = {}.ASpin;
/** @type {[typeof __VLS_components.ASpin, typeof __VLS_components.aSpin, typeof __VLS_components.ASpin, typeof __VLS_components.aSpin, ]} */ ;
// @ts-ignore
const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
    spinning: (__VLS_ctx.isLoading),
}));
const __VLS_18 = __VLS_17({
    spinning: (__VLS_ctx.isLoading),
}, ...__VLS_functionalComponentArgsRest(__VLS_17));
__VLS_19.slots.default;
if (__VLS_ctx.projects.length === 0 && !__VLS_ctx.isLoading) {
    const __VLS_20 = {}.AEmpty;
    /** @type {[typeof __VLS_components.AEmpty, typeof __VLS_components.aEmpty, ]} */ ;
    // @ts-ignore
    const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
        description: "No projects yet. Create your first project to get started!",
    }));
    const __VLS_22 = __VLS_21({
        description: "No projects yet. Create your first project to get started!",
    }, ...__VLS_functionalComponentArgsRest(__VLS_21));
}
else {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "space-y-4" },
    });
    for (const [project] of __VLS_getVForSourceType((__VLS_ctx.projects))) {
        /** @type {[typeof ProjectCard, ]} */ ;
        // @ts-ignore
        const __VLS_24 = __VLS_asFunctionalComponent(ProjectCard, new ProjectCard({
            ...{ 'onEdit': {} },
            ...{ 'onDelete': {} },
            ...{ 'onManageDatasets': {} },
            ...{ 'onAddWorkItem': {} },
            key: (project.id),
            project: (project),
        }));
        const __VLS_25 = __VLS_24({
            ...{ 'onEdit': {} },
            ...{ 'onDelete': {} },
            ...{ 'onManageDatasets': {} },
            ...{ 'onAddWorkItem': {} },
            key: (project.id),
            project: (project),
        }, ...__VLS_functionalComponentArgsRest(__VLS_24));
        let __VLS_27;
        let __VLS_28;
        let __VLS_29;
        const __VLS_30 = {
            onEdit: (__VLS_ctx.handleEdit)
        };
        const __VLS_31 = {
            onDelete: (__VLS_ctx.handleDelete)
        };
        const __VLS_32 = {
            onManageDatasets: (__VLS_ctx.handleManageDatasets)
        };
        const __VLS_33 = {
            onAddWorkItem: (__VLS_ctx.handleAddWorkItem)
        };
        var __VLS_26;
    }
}
var __VLS_19;
var __VLS_7;
/** @type {[typeof ProjectFormModal, ]} */ ;
// @ts-ignore
const __VLS_34 = __VLS_asFunctionalComponent(ProjectFormModal, new ProjectFormModal({
    ...{ 'onSubmit': {} },
    open: (__VLS_ctx.showCreateModal),
    title: "Create New Project",
}));
const __VLS_35 = __VLS_34({
    ...{ 'onSubmit': {} },
    open: (__VLS_ctx.showCreateModal),
    title: "Create New Project",
}, ...__VLS_functionalComponentArgsRest(__VLS_34));
let __VLS_37;
let __VLS_38;
let __VLS_39;
const __VLS_40 = {
    onSubmit: (__VLS_ctx.handleCreate)
};
var __VLS_36;
/** @type {[typeof ProjectFormModal, ]} */ ;
// @ts-ignore
const __VLS_41 = __VLS_asFunctionalComponent(ProjectFormModal, new ProjectFormModal({
    ...{ 'onSubmit': {} },
    open: (__VLS_ctx.showEditModal),
    title: "Edit Project",
    initialValues: (__VLS_ctx.editingProject),
    showStatus: (true),
}));
const __VLS_42 = __VLS_41({
    ...{ 'onSubmit': {} },
    open: (__VLS_ctx.showEditModal),
    title: "Edit Project",
    initialValues: (__VLS_ctx.editingProject),
    showStatus: (true),
}, ...__VLS_functionalComponentArgsRest(__VLS_41));
let __VLS_44;
let __VLS_45;
let __VLS_46;
const __VLS_47 = {
    onSubmit: (__VLS_ctx.handleUpdate)
};
var __VLS_43;
var __VLS_2;
/** @type {__VLS_StyleScopedClasses['max-w-7xl']} */ ;
/** @type {__VLS_StyleScopedClasses['mx-auto']} */ ;
/** @type {__VLS_StyleScopedClasses['px-4']} */ ;
/** @type {__VLS_StyleScopedClasses['sm:px-6']} */ ;
/** @type {__VLS_StyleScopedClasses['lg:px-8']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-8']} */ ;
/** @type {__VLS_StyleScopedClasses['text-4xl']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['inline-flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['i-mdi-plus']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-1']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-4']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            DefaultLayout: DefaultLayout,
            ProjectCard: ProjectCard,
            ProjectFormModal: ProjectFormModal,
            isLoading: isLoading,
            projects: projects,
            showCreateModal: showCreateModal,
            showEditModal: showEditModal,
            editingProject: editingProject,
            handleCreate: handleCreate,
            handleEdit: handleEdit,
            handleUpdate: handleUpdate,
            handleDelete: handleDelete,
            handleManageDatasets: handleManageDatasets,
            handleAddWorkItem: handleAddWorkItem,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
