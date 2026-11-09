# VanillaTracker

Ewidencja sprzętu, licencji i osób - z numerami inwentarzowymi, etykietami
i protokołami przekazania. Napisana w Astro (SSR), działa na Cloudflare
Workers, dane trzyma w bazie D1.

## Funkcje

- Ewidencja sprzętu, licencji i osób (działy, stanowiska) z historią zmian
- Numery inwentarzowe z konfigurowalnym prefiksem (np. `BS-00001`)
- Etykiety PDF 35×25 mm z kodem QR
- Protokół przekazania (PDF A4) z tabelą sprzętu osoby i miejscem na podpis
- Masowe przypisania i wydruk etykiet prosto z listy
- Eksport CSV z tymi samymi filtrami co widok listy

## Uruchomienie lokalne

Wymagany Node.js 20+ i konto Cloudflare.

```bash
npm install
cp .dev.vars.example .dev.vars   # uzupełnij SESSION_SECRET
npm run db:migrate:local
npm run dev
```

Aplikacja działa pod `http://localhost:4321`.

## Wdrożenie

Sekret na produkcji ustawia się raz przez wranglera:

```bash
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

## Dostęp i sesja

Aplikacja nie ma logowania - każdy, kto otworzy adres, ma pełny dostęp.
Jeśli ma być prywatna, ogranicz dostęp przed workerem (np. Cloudflare Access).

Token CSRF i komunikaty jadą w ciasteczku podpisanym HMAC-SHA256 (kluczem
`SESSION_SECRET`, `HttpOnly`, `SameSite=Strict`). Middleware sprawdza token
CSRF przy każdym żądaniu zmieniającym dane.

## Struktura

- `src/pages/` - trasy aplikacji (`assets/`, `licenses/`, `users/`,
  `categories/`, `departments/`)
- `src/middleware.ts` - sesja, CSRF
- `src/lib/db.ts` - zapytania do D1, numeracja tagów, historia
- `src/lib/session.ts`, `crypto.ts` - sesja w podpisanym ciasteczku (WebCrypto)
- `src/lib/labels.ts`, `protocol.ts` - etykiety PDF z kodem QR i protokół przekazania
- `src/styles/app.css` - globalny arkusz MD3
- `migrations/` - schemat bazy i dane startowe
