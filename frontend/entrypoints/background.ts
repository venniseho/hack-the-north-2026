export default defineBackground(() => {
  // Without this the toolbar icon does nothing, since no popup is registered.
  browser.sidePanel
    .setPanelBehavior({ openPanelOnActionClick: true })
    .catch((error) => console.error('Failed to set side panel behavior', error));
});
