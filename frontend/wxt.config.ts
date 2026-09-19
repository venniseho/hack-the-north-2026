import { defineConfig } from 'wxt';
import tailwindcss from '@tailwindcss/vite';

// See https://wxt.dev/api/config.html
export default defineConfig({
  modules: ['@wxt-dev/module-react'],

  vite: () => ({
    plugins: [tailwindcss()],
  }),

  manifest: {
    name: 'Hack the North 2026',
    description: 'Browser assistant powered by the Backboard backend.',
    permissions: ['sidePanel'],
    host_permissions: ['http://localhost:8000/*'],
    // An action is required for the toolbar icon that opens the side panel.
    action: {},
  },
});
