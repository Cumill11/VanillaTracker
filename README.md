# VanillaTracker

Ewidencja sprzętu, licencji i osób — z numerami inwentarzowymi, etykietami
i protokołami przekazania. Napisana w Astro (SSR), działa na Cloudflare
Workers, dane trzyma w bazie D1.

## Funkcje

- Ewidencja sprzętu, licencji i osób (działy, stanowiska) z historią zmian
- Numery inwentarzowe z konfigurowalnym prefiksem (np. `BS-00001`)
- Etykiety PDF 35×25 mm z kodem QR
- Protokół przekazania (PDF A4) z tabelą sprzętu osoby i miejscem na podpis
- Masowe przypisania i wydruk etykiet prosto z listy
- Eksport CSV z tymi samymi filtrami co widok listy
- Logowanie — aplikacja jest w całości prywatna

## Uruchomienie lokalne

Wymagany Node.js 20+ i konto Cloudflare.

```bash
npm install
cp .dev.vars.example .dev.vars   # uzupełnij ADMIN_USERNAME, ADMIN_PASSWORD, SESSION_SECRET
npm run db:migrate:local
npm run dev
```

Aplikacja działa pod `http://localhost:4321`.

## Wdrożenie

Sekrety na produkcji ustawia się raz przez wranglera:

```bash
npx wrangler secret put ADMIN_USERNAME
npx wrangler secret put ADMIN_PASSWORD
npx wrangler secret put SESSION_SECRET
```

Potem migracje i deploy:

```bash
npm run db:migrate:remote
npm run deploy
```
Podczas git push następuje automatyczne wdrożenie na Cloudflare


## Komendy

| Komenda                     | Działanie                       |
| --------------------------- | ------------------------------- |
| `npm run dev`               | Serwer deweloperski             |
| `npm run build`             | Build produkcyjny               |
| `npm run deploy`            | Build i wdrożenie na Cloudflare |
| `npm run db:migrate:local`  | Migracje bazy lokalnej          |
| `npm run db:migrate:remote` | Migracje bazy produkcyjnej      |

## Jak działa logowanie

Jest jedno konto — dane logowania siedzą w sekretach Cloudflare, nie w bazie.
Po zalogowaniu sesja jedzie w ciasteczku podpisanym HMAC-SHA256 (kluczem
`SESSION_SECRET`, `HttpOnly`, `SameSite=Strict`). Middleware sprawdza sesję
i token CSRF przy każdym żądaniu i bez sesji przekierowuje na `/login`.
Logowanie ma limit 5 prób na 5 minut z jednego IP.

## Struktura

- `src/pages/` — trasy aplikacji (`assets/`, `licenses/`, `users/`,
  `categories/`, `departments/`, `login/`)
- `src/middleware.ts` — sesja, CSRF, wymóg zalogowania
- `src/lib/db.ts` — zapytania do D1, numeracja tagów, historia
- `src/lib/auth.ts`, `session.ts`, `crypto.ts` — logowanie i sesja (WebCrypto)
- `src/lib/labels.ts` — etykiety i protokoły PDF z kodem QR
- `src/styles/app.css` — globalny arkusz MD3
- `migrations/` — schemat bazy i dane startowe
