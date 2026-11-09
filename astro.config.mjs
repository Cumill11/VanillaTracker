// @ts-check
import { defineConfig, sessionDrivers } from 'astro/config';
import cloudflare from '@astrojs/cloudflare';

export default defineConfig({
  output: 'server',
  adapter: cloudflare({
    // Bez bindingu Images - aplikacja nie przetwarza obrazów, jedyny zasób
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
  vite: {
    // Obejście withastro/astro#17893 / #17788 (jak w pozostałych projektach):
    // adapter Cloudflare nie dopisuje tych modułów do SSR optimizeDeps, więc przy
    // zimnym cache `.vite` Vite odkrywa je w trakcie żądania i `astro dev` pada.
    // Tylko dev - build produkcyjny ignoruje optimizeDeps.
    ssr: {
      optimizeDeps: {
        include: [
          'astro/app/manifest',
          'astro/assets/services/noop',
          'astro/logger/json',
          'astro/logger/console',
        ],
      },
    },
  },
});
