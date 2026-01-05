<template>
  <div class="min-h-screen bg-gray-50 flex items-center justify-center py-8">
    <div class="max-w-md w-full px-4">
      <a-card class="shadow-lg">
        <div class="text-center mb-6">
          <h1 class="text-2xl font-bold text-gray-900 mb-2">
            Sign Up
          </h1>
          <p class="text-gray-600">
            ML Training Platform
          </p>
        </div>

        <a-form
          :model="formData"
          :rules="rules"
          @finish="handleSignup"
          layout="vertical"
        >
          <a-form-item label="Email" name="email">
            <a-input
              v-model:value="formData.email"
              placeholder="Enter your email"
              size="large"
            >
              <template #prefix>
                <span class="i-mdi-email text-gray-400" />
              </template>
            </a-input>
          </a-form-item>

          <a-form-item label="Phone (optional)" name="phone">
            <a-input
              v-model:value="formData.phone"
              placeholder="Enter your phone number"
              size="large"
            >
              <template #prefix>
                <span class="i-mdi-phone text-gray-400" />
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

          <a-form-item
            label="Confirm Password"
            name="confirmPassword"
          >
            <a-input-password
              v-model:value="formData.confirmPassword"
              placeholder="Confirm your password"
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
              {{ isLoading ? 'Signing Up...' : 'Sign Up' }}
            </a-button>
          </a-form-item>
        </a-form>

        <div v-if="errorMessage" class="mb-4">
          <a-alert
            message="Sign Up Error"
            :description="errorMessage"
            type="error"
            show-icon
            closable
            @close="errorMessage = ''"
          />
        </div>

        <div class="text-center">
          <span class="text-gray-600">Already have an account?</span>
          <router-link
            to="/auth/signin"
            class="text-blue-600 hover:text-blue-800 ml-1"
          >
            Sign In
          </router-link>
        </div>
      </a-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '../../stores/auth';

const router = useRouter();
const authStore = useAuthStore();

const formData = reactive({
  email: '',
  phone: '',
  password: '',
  confirmPassword: '',
});

const rules = {
  email: [
    { required: true, message: 'Email is required' },
    { type: 'email', message: 'Please enter a valid email' },
  ],
  password: [
    { required: true, message: 'Password is required' },
    { min: 6, message: 'Password must be at least 6 characters' },
  ],
  confirmPassword: [
    { required: true, message: 'Please confirm your password' },
    {
      validator: (_rule: any, value: string) => {
        if (value !== formData.password) {
          return Promise.reject('Passwords do not match');
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
      errorMessage.value = result.error || 'Unknown error';
    }
  } catch (error: any) {
    errorMessage.value = error.message || 'Sign up failed';
  } finally {
    isLoading.value = false;
  }
}
</script>

<style scoped>
/* Additional styles if needed */
</style>

