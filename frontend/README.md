# Frontend

Chrome extension built with [WXT](https://wxt.dev) + React + Tailwind v4.
The UI is a side panel that talks to the Python backend in `../backend`.

## Setup

```sh
npm install
cp .env.example .env
```

## Develop

```sh
npm run dev      # launches Chrome with the extension loaded
npm run compile  # typecheck
npm run build    # production build into .output/
```

Click the toolbar icon to open the side panel.

## Layout

| Path | Purpose |
| --- | --- |
| `entrypoints/background.ts` | Service worker; opens the side panel on icon click |
| `entrypoints/sidepanel/` | React app shown in the side panel |
| `lib/api.ts` | Typed client for the backend |
| `wxt.config.ts` | Manifest, permissions, Vite/Tailwind plugins |
