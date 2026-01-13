import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useAuthStore } from '../stores/auth';

// Mock router
vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
}));

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};

  return {
    getItem: (key: string) => store[key] || null,
    setItem: (key: string, value: string) => {
      store[key] = value.toString();
    },
    removeItem: (key: string) => {
      delete store[key];
    },
    clear: () => {
      store = {};
    },
  };
})();

Object.defineProperty(global, 'localStorage', {
  value: localStorageMock,
});

describe('Auth Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorageMock.clear();
    vi.clearAllMocks();
  });

  describe('initialization', () => {
    it('should initialize with empty state when no stored data', () => {
      const authStore = useAuthStore();

      expect(authStore.token).toBe('');
      expect(authStore.user).toBeNull();
      expect(authStore.isAuthenticated).toBe(false);
    });

    it('should load token from localStorage on initialization', () => {
      localStorage.setItem('auth_token', 'test-token');

      const authStore = useAuthStore();

      expect(authStore.token).toBe('test-token');
      expect(authStore.isAuthenticated).toBe(true);
    });
  });

  describe('logout', () => {
    it('should clear token and user data', () => {
      localStorage.setItem('auth_token', 'test-token');
      localStorage.setItem(
        'auth_user',
        JSON.stringify({ id: '1', email: 'test@test.com' })
      );

      const authStore = useAuthStore();
      authStore.logout();

      expect(authStore.token).toBe('');
      expect(authStore.user).toBeNull();
      expect(authStore.isAuthenticated).toBe(false);
    });

    it('should remove items from localStorage', () => {
      localStorage.setItem('auth_token', 'test-token');
      localStorage.setItem('auth_user', JSON.stringify({ id: '1' }));

      const authStore = useAuthStore();
      authStore.logout();

      expect(localStorage.getItem('auth_token')).toBeNull();
      expect(localStorage.getItem('auth_user')).toBeNull();
    });
  });

  describe('isAuthenticated computed', () => {
    it('should return true when token exists', () => {
      localStorage.setItem('auth_token', 'test-token');

      const authStore = useAuthStore();

      expect(authStore.isAuthenticated).toBe(true);
    });

    it('should return false when token is empty', () => {
      const authStore = useAuthStore();

      expect(authStore.isAuthenticated).toBe(false);
    });
  });
});
