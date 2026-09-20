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
    // `scripting` + all-URL host access lets the panel read the Instagram
    // links off the page being checked (only when the user clicks scan).
    // It also covers the localhost backend.
    permissions: ['sidePanel', 'tabs', 'scripting'],
    host_permissions: ['<all_urls>'],
    // An action is required for the toolbar icon that opens the side panel.
    action: {},
  },
});
