import { defineStore } from 'pinia';
import { ref, computed, readonly } from 'vue';
import { useRouter } from 'vue-router';
import { client } from '../api/client';

export const useAuthStore = defineStore('auth', () => {
  const token = ref('');
  const user = ref<any>(null);

  // Initialize from localStorage
  if (typeof window !== 'undefined') {
    token.value = localStorage.getItem('auth_token') || '';
    const userStr = localStorage.getItem('auth_user');
    if (userStr) {
      try {
        user.value = JSON.parse(userStr);
      } catch (e) {
        localStorage.removeItem('auth_user');
      }
    }
  }

  const isAuthenticated = computed(() => !!token.value);

  const router = useRouter();

  async function login(credentials: { identifier: string; password: string }) {
    try {
      const response = await client.api.auth.signin.$post({
        json: credentials,
      });

      if (!response.ok) {
        // HTTP semantics: error response has {code, error}
        const error = await response.json();
        throw new Error(error.error || 'Login failed');
      }

      // HTTP semantics: success response is {token} directly
      const data = await response.json();
      token.value = data.token;
      
      if (typeof window !== 'undefined') {
        localStorage.setItem('auth_token', token.value);
      }

      return { success: true };
    } catch (error) {
      return { success: false, error: (error as Error).message };
    }
  }

  async function signup(credentials: {
    email: string;
    password: string;
    phone?: string;
  }) {
    try {
      const response = await client.api.auth.signup.$post({
        json: credentials,
      });

      if (!response.ok) {
        // HTTP semantics: error response has {code, error}
        const error = await response.json();
        throw new Error(error.error || 'Signup failed');
      }

      // HTTP semantics: success response is {token} directly
      const data = await response.json();
      return { success: true, data };
    } catch (error) {
      return { success: false, error: (error as Error).message };
    }
  }

  function logout() {
    token.value = '';
    user.value = null;
    if (typeof window !== 'undefined') {
      localStorage.removeItem('auth_token');
      localStorage.removeItem('auth_user');
    }
    router.push('/auth/signin');
  }

  async function requestWithToken(url: string, options: RequestInit = {}) {
    const headers: any = {
      'Content-Type': 'application/json',
      ...options.headers,
      Authorization: `Bearer ${token.value}`,
    };

    // Stringify body if it's an object
    let body = options.body;
    if (body && typeof body === 'object' && !(body instanceof FormData)) {
      body = JSON.stringify(body);
    }

    const response = await fetch(url, { ...options, headers, body });
    
    if (response.status === 401) {
      logout();
      throw new Error('Unauthorized');
    }

    return response.json();
  }

  return {
    token: readonly(token),
    user: readonly(user),
    isAuthenticated,
    login,
    signup,
    logout,
    requestWithToken,
  };
});
