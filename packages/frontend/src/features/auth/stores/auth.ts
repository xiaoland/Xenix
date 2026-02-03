import { defineStore } from "pinia";

import { computed, readonly, ref } from "vue";
import { useRouter } from "vue-router";

import type { UserRole } from "@xenix/shared";

import { client } from "@/services/api-client";

const AUTH_TOKEN_KEY = "auth_token";
const AUTH_USER_KEY = "auth_user";
const AUTH_PERMISSIONS_KEY = "auth_permissions";
const REMEMBER_ME_KEY = "auth_remember_me";

export interface AuthUser {
  id: string;
  email: string;
  phone?: string | null;
  role: UserRole;
  isActive: boolean;
}

export const useAuthStore = defineStore("auth", () => {
  const token = ref("");
  const user = ref<AuthUser | null>(null);
  const permissions = ref<string[]>([]);
  const rememberMe = ref(false);

  // Initialize from storage (localStorage or sessionStorage based on rememberMe)
  if (typeof window !== "undefined") {
    const storedRememberMe = localStorage.getItem(REMEMBER_ME_KEY) === "true";
    rememberMe.value = storedRememberMe;

    const storage = storedRememberMe ? localStorage : sessionStorage;
    token.value = storage.getItem(AUTH_TOKEN_KEY) || "";
    const userStr = storage.getItem(AUTH_USER_KEY);
    if (userStr) {
      try {
        user.value = JSON.parse(userStr);
      } catch (e) {
        storage.removeItem(AUTH_USER_KEY);
      }
    }
    const permsStr = storage.getItem(AUTH_PERMISSIONS_KEY);
    if (permsStr) {
      try {
        permissions.value = JSON.parse(permsStr);
      } catch (e) {
        storage.removeItem(AUTH_PERMISSIONS_KEY);
      }
    }
  }

  const isAuthenticated = computed(() => !!token.value && !!user.value);
  const isAdmin = computed(() => user.value?.role === "admin");

  const router = useRouter();

  function getStorage() {
    return rememberMe.value ? localStorage : sessionStorage;
  }

  async function login(credentials: {
    identifier: string;
    password: string;
    rememberMe?: boolean;
  }) {
    try {
      const response = await client.auth.signin.$post({
        json: credentials,
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error((error as any).error || "Login failed");
      }

      const data = (await response.json()) as { token: string; user: AuthUser };
      token.value = data.token;
      user.value = data.user;
      rememberMe.value = credentials.rememberMe || false;

      if (typeof window !== "undefined") {
        const storage = getStorage();
        storage.setItem(AUTH_TOKEN_KEY, token.value);
        storage.setItem(AUTH_USER_KEY, JSON.stringify(user.value));
        localStorage.setItem(REMEMBER_ME_KEY, String(rememberMe.value));
      }

      // Fetch user permissions
      await fetchPermissions();

      return { success: true };
    } catch (error) {
      return { success: false, error: (error as Error).message };
    }
  }

  async function signup(credentials: {
    email: string;
    password: string;
    phone?: string;
    rememberMe?: boolean;
  }) {
    try {
      const response = await client.auth.signup.$post({
        json: credentials,
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error((error as any).error || "Signup failed");
      }

      const data = (await response.json()) as { token: string; user: AuthUser };
      token.value = data.token;
      user.value = data.user;
      rememberMe.value = credentials.rememberMe || false;

      if (typeof window !== "undefined") {
        const storage = getStorage();
        storage.setItem(AUTH_TOKEN_KEY, token.value);
        storage.setItem(AUTH_USER_KEY, JSON.stringify(user.value));
        localStorage.setItem(REMEMBER_ME_KEY, String(rememberMe.value));
      }

      // Fetch user permissions
      await fetchPermissions();

      return { success: true, data };
    } catch (error) {
      return { success: false, error: (error as Error).message };
    }
  }

  async function fetchCurrentUser() {
    try {
      const response = await client.auth.me.$get();
      if (response.ok) {
        const data = (await response.json()) as AuthUser;
        user.value = data;
        if (typeof window !== "undefined") {
          const storage = getStorage();
          storage.setItem(AUTH_USER_KEY, JSON.stringify(user.value));
        }
      }
    } catch (error) {
      console.error("Failed to fetch current user:", error);
    }
  }

  async function fetchPermissions() {
    try {
      const response = await client.auth.permissions.$get();
      if (response.ok) {
        const data = (await response.json()) as { permissions: string[] };
        permissions.value = data.permissions;
        if (typeof window !== "undefined") {
          const storage = getStorage();
          storage.setItem(
            AUTH_PERMISSIONS_KEY,
            JSON.stringify(permissions.value),
          );
        }
      }
    } catch (error) {
      console.error("Failed to fetch permissions:", error);
    }
  }

  function hasPermission(permission: string): boolean {
    if (isAdmin.value) return true;
    return permissions.value.includes(permission);
  }

  function logout() {
    token.value = "";
    user.value = null;
    permissions.value = [];
    rememberMe.value = false;
    if (typeof window !== "undefined") {
      // Clear from both storage types to be safe
      localStorage.removeItem(AUTH_TOKEN_KEY);
      localStorage.removeItem(AUTH_USER_KEY);
      localStorage.removeItem(AUTH_PERMISSIONS_KEY);
      localStorage.removeItem(REMEMBER_ME_KEY);
      sessionStorage.removeItem(AUTH_TOKEN_KEY);
      sessionStorage.removeItem(AUTH_USER_KEY);
      sessionStorage.removeItem(AUTH_PERMISSIONS_KEY);
    }
    router.push("/auth/signin");
  }

  async function requestWithToken(url: string, options: RequestInit = {}) {
    const headers: any = {
      "Content-Type": "application/json",
      ...options.headers,
      Authorization: `Bearer ${token.value}`,
    };

    let body = options.body;
    if (body && typeof body === "object" && !(body instanceof FormData)) {
      body = JSON.stringify(body);
    }

    const response = await fetch(url, { ...options, headers, body });

    if (response.status === 401) {
      logout();
      throw new Error("Unauthorized");
    }

    return response.json();
  }

  return {
    token: readonly(token),
    user: readonly(user),
    permissions: readonly(permissions),
    rememberMe: readonly(rememberMe),
    isAuthenticated,
    isAdmin,
    login,
    signup,
    logout,
    fetchCurrentUser,
    fetchPermissions,
    hasPermission,
    requestWithToken,
  };
});
