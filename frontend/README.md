# Very Frame AI frontend

This is the Next.js client for the Very Frame AI backend. For project setup, supported inputs, environment variables, tests, benchmark procedures, Docker use, and known limitations, see the [repository README](../README.md).

## Local development

```powershell
npm ci
$env:NEXT_PUBLIC_API_URL = "http://localhost:8000"
npm run dev
```

Open <http://localhost:3000>. The backend must be started separately for analysis, sample, result, and insights API behavior.

## Checks

```powershell
npm run lint
npm run build
npm run test:e2e
```

The Playwright configuration starts the frontend development server. Start the backend separately to exercise a successful analysis journey; otherwise the tests check the explicit backend-unavailable experience.
