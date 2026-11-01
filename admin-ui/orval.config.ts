import { defineConfig } from 'orval'

// Клиент staff-API генерируется из схемы бэкенда:
//   python app/manage.py staff_openapi --file admin-ui/openapi/staff.yaml
//   pnpm api:generate
// Сгенерированное не правим руками — оно перезаписывается.
export default defineConfig({
  staff: {
    input: './openapi/staff.yaml',
    output: {
      target: './src/shared/api/generated/staff.ts',
      schemas: './src/shared/api/generated/model',
      client: 'react-query',
      httpClient: 'fetch',
      clean: true,
      override: {
        mutator: { path: './src/shared/api/http.ts', name: 'apiFetch' },
        fetch: { includeHttpResponseReturnType: false },
      },
    },
  },
})
