import path from "path"
import { defineConfig } from "vitest/config"

export default defineConfig({
  test: {
    // Node, not jsdom: these tests cover pure logic — validation schemas,
    // redirect guards, label lookup. Component rendering would need
    // @vitejs/plugin-react, which currently conflicts with the Babel version
    // Next pulls in.
    environment: "node",
    globals: true,
    include: ["__tests__/**/*.test.ts"],
  },
  resolve: {
    alias: { "@": path.resolve(__dirname, ".") },
  },
})
