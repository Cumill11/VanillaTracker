// @ts-check
import { defineConfig, sessionDrivers } from 'astro/config';
import cloudflare from '@astrojs/cloudflare';

export default defineConfig({
  output: 'server',
  adapter: cloudflare({
    // Udostępnia bindings (D1, zmienne z .dev.vars) w `astro dev`.
    platformProxy: { enabled: true },
    // Bez bindingu Images — aplikacja nie przetwarza obrazów, jedyny zasób
    // graficzny to statyczne logo SVG.
    imageService: 'passthrough',
  }),
  // Sesję trzymamy we własnym podpisanym ciasteczku (src/lib/session.ts).
  // Bez tego adapter dorzuciłby wymagany binding KV, którego nie używamy.
  session: { driver: sessionDrivers.null() },
  // Oryginalne URL-e mają końcowy ukośnik (/assets/, /assets/1/).
  // 'ignore' pozwala trafić w trasę z ukośnikiem i bez.
  trailingSlash: 'ignore',
  devToolbar: { enabled: false },
});
