# VanillaTracker

Ewidencja sprzętu i licencji — Astro (SSR) na Cloudflare Workers, dane w D1.
Port aplikacji Flask z `vanillatracker/`, z jedną istotną zmianą: **konta
użytkowników nie logują się do systemu**. Logować może się wyłącznie
administrator, konfigurowany przez sekrety Workera.

## Co się zmieniło względem wersji Flask

| Obszar | Flask | Ta wersja |
|---|---|---|
| Logowanie | konta w bazie, kreator setup, `is_superuser` | jeden administrator z sekretów `ADMIN_USERNAME` / `ADMIN_PASSWORD` |
| Hasła | bcrypt, hash w bazie | hasło wprost w sekrecie Workera, porównanie w stałym czasie |
| Sesja | serwerowa sesja Flaska | podpisane ciasteczko (HMAC-SHA256) |
| Baza | SQLite / MySQL przez SQLAlchemy | Cloudflare D1 (SQL pisany wprost) |
| `users` | dane + hasło + `user_profiles` | tylko dane osób (dział, telefon, stanowisko scalone do `users`) |
| Nazwa sprzętu | osobne pole, puste = producent + model | brak pola; nazwa powstaje z producenta i modelu |
| Prefiks tagów | tabela `settings`, ustawiany w kreatorze | zmienna `TAG_PREFIX` w `wrangler.jsonc` (`BS`) |
| Język | przełącznik PL/EN, ciasteczko `lang` | wyłącznie polski |
| Etykiety PDF | reportlab + qrcode (Python) | pdf-lib + qrcode, QR rysowany wektorowo |
| CSRF | sprawdzane w każdej trasie | sprawdzane centralnie w middleware |

Usunięte trasy: `/setup/`, `/users/<id>/password/`, `/lang/<code>/`. Reszta URL-i
bez zmian.

Historia (`asset_history`) straciła kolumnę `performed_by_id` — operacje wykonuje
zawsze administrator, więc pole nie niosło informacji.

## Wymagania

- Node 20+ i konto Cloudflare

## Uruchomienie od zera

```bash
npm install

# 1. Baza D1 — skopiuj database_id z wyniku do wrangler.jsonc
npm run db:create

# 2. Schemat + dane startowe (10 kategorii, licznik tagów)
npm run db:migrate:local      # lokalnie
npm run db:migrate:remote     # na Cloudflare
```

### Lokalnie

Skopiuj `.dev.vars.example` jako `.dev.vars` i uzupełnij:

```
ADMIN_USERNAME="admin"
ADMIN_PASSWORD="twojeHaslo123"
SESSION_SECRET="losowy-ciag"   # node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"
```

```bash
npm run dev        # http://localhost:4321
npm run preview    # produkcyjny build w prawdziwym workerd
```

### Wdrożenie

```bash
npx wrangler secret put ADMIN_USERNAME
npx wrangler secret put ADMIN_PASSWORD
npx wrangler secret put SESSION_SECRET

npm run deploy
```

Prefiks numerów inwentarzowych ustawia się w `wrangler.jsonc` (`vars.TAG_PREFIX`,
2–4 wielkie litery). Nie jest sekretem, więc nie idzie przez `wrangler secret`.

## Dlaczego bez `nodejs_compat`

Flaga `nodejs_compat` wstawia do środowiska obiekt `process`, po którym Astro
rozpoznaje Node i renderuje strony przez async-iterable. `Response` w workerd
takiego ciała nie przyjmuje i odsyła `[object Object]` zamiast HTML-a. Aplikacja
korzysta wyłącznie z API dostępnych w Workers (WebCrypto, fetch), a `pdf-lib`
i `qrcode` to czysty JavaScript — flaga jest zbędna. Nie dodawaj jej.

## Struktura

```
migrations/                  schemat D1 + dane startowe, kolejne zmiany schematu
src/middleware.ts            sesja, CSRF, wymóg zalogowania
src/lib/
  auth.ts                    logowanie administratora, limit prób
  crypto.ts                  HMAC, porównania w stałym czasie (WebCrypto)
  session.ts                 sesja w podpisanym ciasteczku
  db.ts                      typy wierszy, numeracja tagów, historia
  entities.ts                pola formularzy sprzętu/licencji/osób i ich kolumny
  sql.ts                     INSERT/UPDATE z mapy kolumn
  env.ts                     bindings i sekrety (cloudflare:workers)
  labels.ts                  etykiety PDF 35×25 mm z kodem QR
  i18n.ts                    teksty interfejsu (polskie)
  forms.ts, format.ts, pagination.ts, notes.ts
src/styles/app.css           globalny arkusz MD3 (layout + strona logowania)
src/layouts/Base.astro       layout MD3 (port base.html)
src/components/              FormShell/FormCard/FormField, Field, StatusChip,
                             Pagination, HistoryTimeline, formularze encji
src/pages/                   trasy 1:1 z wersją Flask
```

## Gdzie co dopisać

- **nowe pole encji** — nazwa w `*_FIELDS` i jedna linia w `columns()`
  (`src/lib/entities.ts`), potem `<FormField>` w komponencie formularza
  i kolumna w migracji. Typ danych formularza wynika z listy pól,
  więc nie ma czego aktualizować osobno.
- **nowa strona** — katalog w `src/pages/` (trasa = ścieżka pliku), treść
  w `<Base>`; middleware sam wymusi logowanie i sprawdzi token CSRF.

## Ułatwienia w codziennej pracy

Dodane po przejrzeniu prawdziwych danych — prawie każdy sprzęt trafia od razu
do konkretnej osoby, a pola zakupowe zostają puste:

- **Przypisanie przy dodawaniu** — pole „przypisz od razu" w formularzu nowego
  sprzętu ustawia osobę, datę i status oraz zapisuje wpis w historii.
- **Zwinięta sekcja „Dane zakupu"** — data, cena i gwarancja są pod jednym
  kliknięciem; przy edycji rozwijają się same, jeśli coś zawierają.
- **`Dodaj kolejny taki sam`** — przycisk na karcie sprzętu otwiera formularz
  wypełniony jego danymi (bez numeru seryjnego), pod adresem `/assets/new/?clone=<id>`.
- **Masowe przypisanie** — po zaznaczeniu pozycji na liście pojawia się pasek
  z wyborem osoby; te same zaznaczenia obsługują wydruk etykiet (`formaction`).
- **Eksport CSV** (`/assets/export/`) — z tymi samymi filtrami co widok listy,
  średniki i znacznik BOM, więc polski Excel otwiera plik od razu w kolumnach.
- **Protokół przekazania** (`/users/<id>/protocol/`) — PDF A4 z danymi osoby,
  tabelą jej sprzętu, oświadczeniem i miejscem na podpisy.

### Czcionka protokołu

Wbudowane czcionki pdf-lib używają kodowania WinAnsi, które nie zawiera polskich
znaków. Protokół osadza więc okrojony Droid Sans (Apache 2.0) — tylko znaki
łacińskie i polskie, 28 kB. Plik binarny nie przejdzie przez pakowanie Workera,
więc trafia do kodu jako base64:

```bash
node scripts/font-to-module.mjs src/assets/DroidSans-latin-pl.ttf src/assets/protocolFont.ts
```

Etykiety nie potrzebują tej czcionki — zawierają wyłącznie numer inwentarzowy.

## Przeniesienie danych ze starej aplikacji

Zrzut MariaDB/MySQL z wersji Flask zamienia się na SQL dla D1 skryptem
`scripts/import-mysql-dump.mjs`. Skrypt mapuje stary schemat na nowy: scala
`user_profiles` do `users`, pomija kolumny, których już nie ma (`assets.name`,
`assets.location`, `categories.description`, `asset_history.performed_by_id`,
hasła), pomija tabele `settings` i `login_attempts`, a znaczniki czasu zapisuje
w ISO-8601 (stara aplikacja trzymała czas uniwersalny, nowa formatuje go do
strefy Europe/Warsaw).

```bash
node scripts/import-mysql-dump.mjs zrzut.sql > import.sql
npx wrangler d1 execute vanillatracker --local  --file import.sql   # lokalnie
npx wrangler d1 execute vanillatracker --remote --file import.sql   # na Cloudflare
```

Import **czyści tabele przed wstawieniem**, więc nadaje się do przeniesienia
danych na start, a nie do dokładania ich do istniejącej bazy.

## Zapytania do bazy

Każde odpytanie D1 to osobne okrążenie po sieci, więc strony wysyłają wszystko,
co potrzebne, jednym `db.batch()`. Wyjątkiem są sytuacje, w których kolejne
zapytanie zależy od wyniku poprzedniego (np. przypisanie licencji sprawdza
najpierw, czy licencja istnieje).

Stronicowanie (`src/lib/pagination.ts`) liczy wszystkie pasujące wiersze funkcją
okna `COUNT(*) OVER ()` w tym samym zapytaniu, które pobiera stronę — bez
osobnego `SELECT COUNT(*)`. Warunek `WHERE` jest więc zapisany raz.

Ciało formularza parsuje middleware i podaje stronom przez `Astro.locals.form`;
wcześniej każde żądanie POST czytało je dwa razy.

## Wygląd i responsywność

Cały arkusz stylów jest w `src/styles/app.css` — importują go layout i strona
logowania, więc kolory i komponenty definiujemy raz. Wyjątkiem jest strona błędu
(`src/lib/errorPage.ts`) z własnym, minimalnym CSS w treści dokumentu: bywa
zwracana z middleware i musi wyglądać poprawnie nawet bez zasobów statycznych.

Punkty łamania układu:

| Szerokość | Układ |
|---|---|
| > 1024 px | szyna nawigacji 80 px z podpisami, tabele, siatka szczegółów 2-kolumnowa |
| ≤ 1024 px | szyna 64 px, same ikony |
| ≤ 900 px | listy jako karty zamiast tabel, siatki jednokolumnowe |
| ≤ 640 px | nawigacja przenosi się na dół ekranu, powiększone cele dotknięcia |

## Bezpieczeństwo

- sesja w ciasteczku podpisanym HMAC-SHA256 (`HttpOnly`, `SameSite=Strict`, `Secure`, 7 dni)
- token CSRF w każdym formularzu, weryfikowany w middleware dla POST/PUT/PATCH/DELETE
- wbudowana kontrola nagłówka `Origin` z Astro (domyślnie włączona)
- nagłówki `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`,
  `Referrer-Policy: strict-origin-when-cross-origin` — ustawiane w **dwóch**
  miejscach, bo Cloudflare stosuje `public/_headers` wyłącznie do zasobów
  statycznych; strony generowane przez workera oznacza `src/middleware.ts`
- limit logowania: 5 prób na 5 minut z jednego IP (tabela `login_attempts`)
- login i hasło porównywane w stałym czasie, na skrótach SHA-256 — czas
  odpowiedzi nie zdradza nawet długości sekretu
- zapytania wyłącznie parametryzowane; `ORDER BY` z białej listy
