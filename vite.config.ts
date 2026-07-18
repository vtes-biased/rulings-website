import { defineConfig } from "vite"
import { svelte } from "@sveltejs/vite-plugin-svelte"
import tailwindcss from "@tailwindcss/vite"

// Entry points keep stable, hashless names because the Jinja templates reference them
// directly (e.g. /static/dist/js/index.js, /static/dist/css/app.css). Shared chunks and
// fonts get hashes. base is set so url() references inside app.css resolve under the
// StaticFiles mount at /static/dist/.
export default defineConfig({
    base: "/static/dist/",
    plugins: [svelte(), tailwindcss()],
    build: {
        outDir: "src/vtesrulings/static/dist",
        emptyOutDir: true,
        rollupOptions: {
            input: {
                index: "src/front/js/index.ts",
                groups: "src/front/js/groups.ts",
                admin: "src/front/js/admin.ts",
                proposal: "src/front/js/proposal.ts",
                app: "src/front/css/app.css",
                island: "src/front/island/main.ts",
            },
            output: {
                entryFileNames: "js/[name].js",
                chunkFileNames: "js/[name]-[hash].js",
                assetFileNames: (info) =>
                    info.names[0]?.endsWith(".css")
                        ? "css/[name][extname]"
                        : "assets/[name]-[hash][extname]",
            },
        },
    },
})
