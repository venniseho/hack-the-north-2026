import { defineConfig } from "wxt";
import tailwindcss from "@tailwindcss/vite";

// See https://wxt.dev/api/config.html
export default defineConfig({
  modules: ["@wxt-dev/module-react"],

  vite: () => ({
    plugins: [tailwindcss()],
  }),

  manifest: {
    name: "Hack the North 2026",
    description: "Browser assistant powered by the Backboard backend.",
    // `scripting` + all-URL host access lets the panel read the Instagram
    // links off the page being checked (only when the user clicks scan).
    // It also covers the localhost backend.
    permissions: ["sidePanel", "tabs", "scripting", "scripting", "activeTab"],

    // `<all_urls>` is required, not preferred. `activeTab` does not cover this
    // flow: opening the side panel through `openPanelOnActionClick` consumes
    // the action click without granting activeTab on the tab, so
    // `executeScript` is refused with "Extension manifest must request
    // permission to access this host". Measured against the built extension in
    // Chrome - activeTab alone fails on an ordinary http page, the same page
    // extracts 3 reviews with this line present.
    //
    // This grants the *ability* to inject, not a standing content script. The
    // extractor still runs only on the tab being analysed, only when the user
    // presses the button. Tightening this to optional_host_permissions, asked
    // for on first use, is the follow-up.
    host_permissions: ["<all_urls>", "<all_urls>"],
    // An action is required for the toolbar icon that opens the side panel.
    action: {},
  },
});
