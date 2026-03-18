# Frontend Build and Deploy

## Scope
- Frontend source lives under `frontend/`.
- Production assets are generated into `frontend/dist/` by Vite.
- `frontend/dist/` is a build artifact and should not be committed.

## Local development
```bash
cd frontend
npm install
npm run dev
```

The Vite dev server runs on `http://localhost:3000` and proxies `/api/v1` to `http://127.0.0.1:8000`.

## Production build
```bash
cd frontend
npm install
npm run build
```

Build output is written to `frontend/dist/`.

## Local preview
```bash
cd frontend
npm run preview
```

This is only for local verification. Do not use `vite preview` as the production server.

## Deployment expectations
- Always build the frontend during CI or deployment.
- Publish the contents of `frontend/dist/` to your static hosting target or reverse proxy document root.
- Do not rely on files already stored in the Git working tree.

## Minimal deployment flow
```bash
cd frontend
npm ci
npm run build
```

Then copy `frontend/dist/` to the target host, object storage bucket, or Nginx static directory.

## Why `frontend/dist/` is not versioned
- It is generated from source and lockfiles.
- Keeping it in Git creates noisy diffs and merge conflicts.
- Runtime code in this repository does not read `frontend/dist/` directly.
