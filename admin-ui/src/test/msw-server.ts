import { setupServer } from 'msw/node'

/** Shared MSW server for unit tests; add handlers per test with `server.use(...)`. */
export const server = setupServer()
