import test from 'node:test';
import assert from 'node:assert/strict';
import { clearAuthSession } from './session.ts';
import { queryClient } from '../../lib/queryClient.ts';

test('logout clears tokens and query cache', async () => {
  globalThis.localStorage = {
    store: {},
    getItem(key) {
      return this.store[key] ?? null;
    },
    setItem(key, value) {
      this.store[key] = String(value);
    },
    removeItem(key) {
      delete this.store[key];
    },
    clear() {
      this.store = {};
    },
  };

  localStorage.setItem('access_token', 'token-123');
  localStorage.setItem('refresh_token', 'refresh-456');
  queryClient.setQueryData(['currentUser'], { id: 'user-1' });
  queryClient.setQueryData(['todos'], { items: [], total: 0 });

  clearAuthSession();

  assert.equal(localStorage.getItem('access_token'), null);
  assert.equal(localStorage.getItem('refresh_token'), null);
  assert.equal(queryClient.getQueryCache().findAll().length, 0);
});
