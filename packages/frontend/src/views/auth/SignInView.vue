<template>
  <div class="min-h-screen bg-gray-50 flex items-center justify-center py-8">
    <div class="max-w-md w-full px-4">
      <a-card class="shadow-lg">
        <div class="text-center mb-6">
          <h1 class="text-2xl font-bold text-gray-900 mb-2">Sign In</h1>
          <p class="text-gray-600">ML Training Platform</p>
        </div>

        <a-form
          :model="formData"
          :rules="rules"
          layout="vertical"
          @finish="handleSignin"
        >
          <a-form-item label="Email or Phone" name="identifier">
            <a-input
              v-model:value="formData.identifier"
              placeholder="Enter your email or phone"
              size="large"
            >
              <template #prefix>
                <span class="i-mdi-account text-gray-400" />
              </template>
            </a-input>
          </a-form-item>

          <a-form-item label="Password" name="password">
            <a-input-password
              v-model:value="formData.password"
              placeholder="Enter your password"
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
              {{ isLoading ? 'Signing In...' : 'Sign In' }}
            </a-button>
          </a-form-item>
        </a-form>

        <div v-if="errorMessage" class="mb-4">
          <a-alert
            message="Sign In Error"
            :description="errorMessage"
            type="error"
            show-icon
            closable
            @close="errorMessage = ''"
          />
        </div>

        <div v-if="successMessage" class="mb-4">
          <a-alert
            message="Signup Successful! Please sign in."
            type="success"
            show-icon
            closable
            @close="successMessage = false"
          />
        </div>

        <div class="text-center">
          <span class="text-gray-600">Don't have an account?</span>
          <router-link
            to="/auth/signup"
            class="text-blue-600 hover:text-blue-800 ml-1"
          >
            Sign Up
          </router-link>
        </div>
      </a-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { useAuthStore } from '../../stores/auth';

const router = useRouter();
const route = useRoute();
const authStore = useAuthStore();

const formData = reactive({
  identifier: '',
  password: '',
});

const rules = {
  identifier: [{ required: true, message: 'Email or phone is required' }],
  password: [{ required: true, message: 'Password is required' }],
};

const isLoading = ref(false);
const errorMessage = ref('');
const successMessage = ref(false);

// Check for signup success query param
onMounted(() => {
  if (route.query.signup === 'success') {
    successMessage.value = true;
  }
});

async function handleSignin() {
  isLoading.value = true;
  errorMessage.value = '';

  try {
    const result = await authStore.login(formData);

    if (result.success) {
      // Get intended route from sessionStorage or default to home
      const intendedRoute = sessionStorage.getItem('intendedRoute') || '/';
      sessionStorage.removeItem('intendedRoute');
      await router.push(intendedRoute);
    } else {
      errorMessage.value = result.error || 'Unknown error';
    }
  } catch (error: any) {
    errorMessage.value = error.message || 'Sign in failed';
  } finally {
    isLoading.value = false;
  }
}
</script>

<style scoped>
/* Additional styles if needed */
</style>
