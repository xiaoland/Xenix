<template>
  <default-layout>
    <div class="p-6">
      <div class="flex justify-between items-center mb-6">
        <h1 class="text-2xl font-bold">{{ $t("users.title") }}</h1>
        <a-button type="primary" @click="showCreateModal = true">
          <span class="i-mdi-plus mr-1" />
          {{ $t("users.createUser") }}
        </a-button>
      </div>

      <a-table
        :columns="columns"
        :data-source="users"
        :loading="isLoading"
        row-key="id"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'role'">
            <a-tag :color="record.role === 'admin' ? 'red' : 'blue'">
              {{ record.role }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'isActive'">
            <a-tag :color="record.isActive ? 'green' : 'orange'">
              {{ record.isActive ? $t("users.active") : $t("users.inactive") }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'actions'">
            <a-space>
              <a-button type="link" @click="handleEdit(record)">
                {{ $t("common.edit") }}
              </a-button>
              <a-button type="link" danger @click="handleDelete(record)">
                {{ $t("common.delete") }}
              </a-button>
            </a-space>
          </template>
        </template>
      </a-table>
    </div>

    <!-- Create/Edit User Modal -->
    <a-modal
      v-model:open="showCreateModal"
      :title="editingUser ? $t('users.editUser') : $t('users.createUser')"
      @ok="handleSave"
      @cancel="resetForm"
    >
      <a-form :model="formData" layout="vertical">
        <a-form-item :label="$t('auth.signup.email')" name="email">
          <a-input v-model:value="formData.email" />
        </a-form-item>
        <a-form-item :label="$t('auth.signup.phone')" name="phone">
          <a-input v-model:value="formData.phone" />
        </a-form-item>
        <a-form-item :label="$t('users.role')" name="role">
          <a-select v-model:value="formData.role">
            <a-select-option value="user">{{
              $t("users.roleUser")
            }}</a-select-option>
            <a-select-option value="admin">{{
              $t("users.roleAdmin")
            }}</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item :label="$t('users.status')" name="isActive">
          <a-switch v-model:checked="formData.isActive" />
        </a-form-item>
        <a-form-item
          v-if="!editingUser"
          :label="$t('auth.signup.password')"
          name="password"
        >
          <a-input-password v-model:value="formData.password" />
        </a-form-item>
      </a-form>
    </a-modal>
  </default-layout>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive } from "vue";
import { useI18n } from "vue-i18n";
import { message, Modal } from "ant-design-vue";
import DefaultLayout from "../../common/components/DefaultLayout.vue";
import { useAuthStore } from "../stores";
import type { User } from "../types";

const { t } = useI18n();
const authStore = useAuthStore();

const users = ref<User[]>([]);
const isLoading = ref(false);
const showCreateModal = ref(false);
const editingUser = ref<User | null>(null);

const formData = reactive({
  email: "",
  phone: "",
  role: "user" as "admin" | "user",
  isActive: true,
  password: "",
});

const columns = [
  { title: t("users.email"), dataIndex: "email", key: "email" },
  { title: t("users.phone"), dataIndex: "phone", key: "phone" },
  { title: t("users.role"), key: "role" },
  { title: t("users.status"), key: "isActive" },
  { title: t("common.actions"), key: "actions" },
];

onMounted(() => {
  fetchUsers();
});

async function fetchUsers() {
  isLoading.value = true;
  try {
    const response = await authStore.requestWithToken("/api/auth/users");
    users.value = response;
  } catch (error) {
    message.error(t("users.fetchError"));
  } finally {
    isLoading.value = false;
  }
}

function handleEdit(user: User) {
  editingUser.value = user;
  formData.email = user.email;
  formData.phone = user.phone || "";
  formData.role = user.role;
  formData.isActive = user.isActive;
  formData.password = "";
  showCreateModal.value = true;
}

function handleDelete(user: User) {
  Modal.confirm({
    title: t("users.deleteConfirm"),
    content: t("users.deleteConfirmContent", { email: user.email }),
    onOk: async () => {
      try {
        await authStore.requestWithToken(`/api/auth/users/${user.id}`, {
          method: "DELETE",
        });
        message.success(t("users.deleteSuccess"));
        fetchUsers();
      } catch (error) {
        message.error(t("users.deleteError"));
      }
    },
  });
}

async function handleSave() {
  try {
    if (editingUser.value) {
      await authStore.requestWithToken(
        `/api/auth/users/${editingUser.value.id}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            email: formData.email,
            phone: formData.phone,
            role: formData.role,
            isActive: formData.isActive,
          }),
        },
      );
      message.success(t("users.updateSuccess"));
    } else {
      await authStore.requestWithToken("/api/auth/signup", {
        method: "POST",
        body: JSON.stringify({
          email: formData.email,
          phone: formData.phone,
          password: formData.password,
        }),
      });
      message.success(t("users.createSuccess"));
    }
    showCreateModal.value = false;
    resetForm();
    fetchUsers();
  } catch (error) {
    message.error(t("users.saveError"));
  }
}

function resetForm() {
  editingUser.value = null;
  formData.email = "";
  formData.phone = "";
  formData.role = "user";
  formData.isActive = true;
  formData.password = "";
}
</script>
