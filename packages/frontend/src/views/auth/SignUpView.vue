<template>
  <div class="min-h-screen bg-gray-50 flex items-center justify-center py-8">
    <div class="max-w-md w-full px-4">
      <a-card class="shadow-lg">
        <div class="text-center mb-6">
          <h1 class="text-2xl font-bold text-gray-900 mb-2">
            {{ $t('auth.signup.title') }}
          </h1>
          <p class="text-gray-600">{{ $t('app.subtitle') }}</p>
        </div>

        <a-form
          :model="formData"
          :rules="rules"
          layout="vertical"
          @finish="handleSignup"
        >
          <a-form-item :label="$t('auth.signup.email')" name="email">
            <a-input
              v-model:value="formData.email"
              :placeholder="$t('auth.signup.emailPlaceholder')"
              size="large"
            >
              <template #prefix>
                <span class="i-mdi-email text-gray-400" />
              </template>
            </a-input>
          </a-form-item>

          <a-form-item :label="$t('auth.signup.phone')" name="phone">
            <a-input
              v-model:value="formData.phone"
              :placeholder="$t('auth.signup.phonePlaceholder')"
              size="large"
            >
              <template #prefix>
                <span class="i-mdi-phone text-gray-400" />
              </template>
            </a-input>
          </a-form-item>

          <a-form-item :label="$t('auth.signup.password')" name="password">
            <a-input-password
              v-model:value="formData.password"
              :placeholder="$t('auth.signup.passwordPlaceholder')"
              size="large"
            >
              <template #prefix>
                <span class="i-mdi-lock text-gray-400" />
              </template>
            </a-input-password>
          </a-form-item>

          <a-form-item
            :label="$t('auth.signup.confirmPassword')"
            name="confirmPassword"
          >
            <a-input-password
              v-model:value="formData.confirmPassword"
              :placeholder="$t('auth.signup.confirmPasswordPlaceholder')"
              size="large"
            >
              <template #prefix>
                <span class="i-mdi-lock text-gray-400" />
              </template>
            </a-input-password>
          </a-form-item>

          <a-form-item>
            <a-button
              type="primary"
              html-type="submit"
              size="large"
              block
              :loading="isLoading"
            >
              {{
                isLoading
                  ? $t('auth.signup.signingUp')
                  : $t('auth.signup.signupButton')
              }}
            </a-button>
          </a-form-item>
        </a-form>

        <div v-if="errorMessage" class="mb-4">
          <a-alert
            :message="$t('auth.signup.signupError')"
            :description="errorMessage"
            type="error"
            show-icon
            closable
            @close="errorMessage = ''"
          />
        </div>

        <div class="text-center">
          <span class="text-gray-600">{{ $t('auth.signup.haveAccount') }}</span>
          <router-link
            to="/auth/signin"
            class="text-blue-600 hover:text-blue-800 ml-1"
          >
            {{ $t('auth.signup.signinLink') }}
          </router-link>
        </div>
      </a-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRouter } from 'vue-router';

import { useAuthStore } from '../../stores/auth';

const router = useRouter();
const authStore = useAuthStore();
const { t } = useI18n();

const formData = reactive({
  email: '',
  phone: '',
  password: '',
  confirmPassword: '',
});

const rules = {
  email: [
    { required: true, message: t('auth.signup.emailRequired') },
    { type: 'email' as const, message: t('auth.signup.emailInvalid') },
  ],
  password: [
    { required: true, message: t('auth.signup.passwordRequired') },
    { min: 6, message: t('auth.signup.passwordMin') },
  ],
  confirmPassword: [
    { required: true, message: t('auth.signup.confirmPasswordRequired') },
    {
      validator: (_rule: any, value: string) => {
        if (value !== formData.password) {
          return Promise.reject(t('auth.signup.passwordsNotMatch'));
        }
        return Promise.resolve();
      },
    },
  ],
};

const isLoading = ref(false);
const errorMessage = ref('');

async function handleSignup() {
  isLoading.value = true;
  errorMessage.value = '';

  try {
    const result = await authStore.signup({
      email: formData.email,
      password: formData.password,
      phone: formData.phone || undefined,
    });

    if (result.success) {
      // Redirect to signin with success message
      await router.push('/auth/signin?signup=success');
    } else {
      errorMessage.value = result.error || t('auth.signup.signupError');
    }
  } catch (error: any) {
    errorMessage.value = error.message || t('auth.signup.signupError');
  } finally {
    isLoading.value = false;
  }
}
</script>

<style scoped>
/* Additional styles if needed */
</style>
