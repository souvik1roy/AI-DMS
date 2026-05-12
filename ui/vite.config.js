import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
// Vite serves the UI; Tauri opens this URL in dev and loads the bundled `dist/` in prod.
export default defineConfig({
    plugins: [react()],
    clearScreen: false,
    server: {
        port: 5173,
        strictPort: true,
        host: "127.0.0.1",
    },
    resolve: {
        alias: [{ find: "@", replacement: "/src" }],
    },
    build: {
        outDir: "dist",
        sourcemap: false,
        minify: "esbuild",
        target: "esnext",
        emptyOutDir: true,
    },
});
