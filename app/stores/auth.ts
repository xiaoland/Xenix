import { defineStore } from "pinia";
import { ref, computed, readonly } from "vue";
import { useRouter } from "#app";

export const useAuthStore = defineStore("auth", () => {
  const token = ref("");
  const user = ref(null);

  // Initialize from localStorage only on client
  if (import.meta.client) {
    token.value = localStorage.getItem("token") || "";
    const userStr = localStorage.getItem("user");
    if (userStr) {
      try {
        user.value = JSON.parse(userStr);
      } catch (e) {
        // Invalid JSON, clear it
        localStorage.removeItem("user");
      }
    }
  }

  const isAuthenticated = computed(() => !!token.value);

  const router = useRouter();

  async function login(credentials: { identifier: string; password: string }) {
    try {
      const response = await $fetch("/api/auth/signin", {
        method: "POST",
        body: credentials,
      });

      if (response.error) {
        throw new Error(response.error);
      }

      token.value = response.token;
      user.value = response.user;
      if (import.meta.client) {
        localStorage.setItem("token", token.value);
        localStorage.setItem("user", JSON.stringify(user.value));
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
      const response = await $fetch("/api/auth/signup", {
        method: "POST",
        body: credentials,
      });

      if (response.error) {
        throw new Error(response.error);
      }

      return { success: true, data: response };
    } catch (error) {
      return { success: false, error: (error as Error).message };
    }
  }

  function logout() {
    token.value = "";
    user.value = null;
    if (import.meta.client) {
      localStorage.removeItem("token");
      localStorage.removeItem("user");
    }
    router.push("/signin");
  }

  async function fetchWithToken(url: string, options: any = {}) {
    const headers = {
      ...options.headers,
      Authorization: `Bearer ${token.value}`,
    };
    return $fetch(url, { ...options, headers });
  }

  return {
    token: readonly(token),
    user: readonly(user),
    isAuthenticated,
    login,
    signup,
    logout,
    requestWithToken: fetchWithToken,
  };
});
