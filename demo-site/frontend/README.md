# DataRoot Demo Frontend

React/Vite frontend for the Nexus-first DataRoot demo app.

## Run

```bash
npm install
npm run dev
```

Default local URL: `http://localhost:7668`.

Useful routes:

- `/nexusag`: Nexus Ag master and module carousel.
- `/demo`: smaller fixture switcher.
- `/docs`: in-app docs page.

## Build

```bash
npm run build
```

The frontend reads bundled `.dfd.json` fixtures from `public/` and tries to
register them with the backend through `/projects/import` so validation, save,
chat, and export routes work when the backend is running.
