import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    // Loopback only (Vite's default). Binding every interface with `host: true`
    // is what LAN access needs, but it also publishes /auth/dev-login — which
    // mints a JWT for any email with no credentials — to everyone on the
    // network. Turn it on deliberately for a LAN session, not by default.
    // See the LAN section in the repo README.
  },
})
