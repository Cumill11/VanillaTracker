# VanillaTracker

System ewidencji sprzętu IT zbudowany na FastAPI. Umożliwia zarządzanie sprzętem, licencjami i użytkownikami z podziałem na działy.

## Funkcje

- Kreator pierwszego uruchomienia — tworzy konto administratora i konfiguruje prefiks numerów inwentarzowych
- Ewidencja sprzętu z numerami IT-XXXXX (prefiks konfigurowalny) i kodami QR na etykietach PDF
- Pola specyficzne dla kategorii: CPU/RAM/dysk (laptop, desktop), numer telefonu (telefon/tablet), tusz (drukarka)
- Przypisywanie sprzętu do osoby lub działu z historią operacji
- Zarządzanie licencjami (miejsca, daty wygaśnięcia, przypisanie do użytkowników)
- Zarządzanie użytkownikami z podziałem na działy
- Paginacja, filtrowanie i wyszukiwanie na wszystkich listach
- Sesyjne komunikaty flash i ochrona CSRF
- Interfejs w Material Design 3 (dark mode)
- Przełącznik języka PL/EN — preferencja przechowywana w ciasteczku

## Wymagania

- Python 3.12+
- Docker + Docker Compose (opcjonalnie)

## Uruchomienie lokalnie

```bash
# Sklonuj repo i wejdź do folderu
cd vanillatracker

# Utwórz środowisko wirtualne
python -m venv venv
source venv/bin/activate

# Zainstaluj zależności
pip install -r requirements.txt

# Utwórz plik .env
cp .env.example .env
# Uzupełnij SECRET_KEY w .env

# Uruchom serwer
uvicorn app.main:app --reload
```

Aplikacja dostępna pod `http://localhost:8000`. Przy pierwszym uruchomieniu kreator na `/setup/` poprowadzi przez tworzenie konta administratora i wybór prefiksu numerów inwentarzowych. Baza danych i tabele są tworzone automatycznie przy starcie.

## Uruchomienie przez Docker

```bash
# Uzupełnij .env (skopiuj z .env.example i zmień hasła)
cp .env.example .env

# Uruchom
docker compose up -d
```

Obraz pobierany z `ghcr.io/cumill11/vanilla-tracker:latest`. Przy pierwszym uruchomieniu kreator jest dostępny pod `http://localhost:8000/setup/`.

## Konfiguracja (.env)

| Zmienna | Opis | Domyślnie |
|---|---|---|
| `SECRET_KEY` | Klucz sesji — zmień przed wdrożeniem | *(brak)* |
| `DATABASE_URL` | URL bazy danych | `sqlite:///./db.sqlite3` |
| `DB_HOST` | Host MySQL/MariaDB | *(brak)* |
| `DB_PORT` | Port MySQL/MariaDB | `3306` |
| `DB_NAME` | Nazwa bazy | `vanillatracker` |
| `DB_USER` | Użytkownik bazy | `root` |
| `DB_PASSWORD` | Hasło użytkownika | *(brak)* |
| `HTTPS_ONLY` | Wymusza HTTPS dla ciasteczka sesji | `false` |

Jeśli ustawiony jest `DATABASE_URL`, pozostałe zmienne `DB_*` są ignorowane. Jeśli nie ustawiono żadnego, aplikacja używa SQLite.

### Przykład dla MySQL

```env
SECRET_KEY=losowy-klucz-min-32-znaki
DATABASE_URL=mysql+pymysql://user:haslo@localhost:3306/vanillatracker
```

### Przykład dla SQLite (dev)

```env
SECRET_KEY=losowy-klucz-min-32-znaki
# DATABASE_URL nie jest potrzebne — SQLite używany domyślnie
```

## Testy

```bash
# Uruchom wszystkie testy
python -m pytest tests/

# Konkretny plik
python -m pytest tests/test_assets.py

# Zatrzymaj przy pierwszym błędzie
python -m pytest tests/ -x
```

Testy używają osobnej bazy SQLite (`test_vanillatracker.db`) tworzonej i usuwanej automatycznie. Nie wymagają uruchomionej aplikacji ani zewnętrznej bazy.

## Struktura projektu

```
app/
├── main.py          # Aplikacja FastAPI, middleware, filtry Jinja2
├── models.py        # Modele SQLAlchemy
├── database.py      # Silnik bazy i sesja
├── auth.py          # Haszowanie haseł, CSRF, autentykacja
├── deps.py          # Zależności FastAPI (login_required, ctx)
├── flash.py         # Komunikaty flash przez sesję
├── i18n.py          # Słowniki tłumaczeń PL/EN i context processor
├── pagination.py    # Paginacja zapytań
├── label_pdf.py     # Generowanie etykiet PDF z QR
└── routers/
    ├── setup.py     # Kreator pierwszego uruchomienia
    ├── auth.py      # Logowanie / wylogowanie
    ├── dashboard.py # Strona główna
    ├── assets.py    # CRUD sprzętu, przypisanie, etykiety
    ├── licenses.py  # CRUD licencji, przypisanie użytkowników
    ├── users.py     # CRUD użytkowników i haseł
    └── categories.py# Kategorie i działy
templates/           # Szablony Jinja2
static/              # CSS, JS, ikony, logo
tests/               # Testy pytest (69 testów)
```

## Bezpieczeństwo

- Kreator pierwszego uruchomienia — aplikacja niedostępna bez konta admina
- Tokeny CSRF weryfikowane na każdym żądaniu POST
- Hasła haszowane bcryptem
- Rate limiting logowania: 5 prób / 5 minut per IP
- Ochrona przed open redirect przy przekierowaniu po logowaniu
- `same_site=strict` na ciasteczku sesji
- `https_only` konfigurowalny przez `HTTPS_ONLY=true`
- Autoescape włączony w szablonach Jinja2

---

# VanillaTracker (English)

IT asset management system built with FastAPI. Manage hardware, licenses and users across departments.

## Features

- First-run setup wizard — creates an admin account and configures the asset tag prefix
- Asset tracking with customisable tag numbers (e.g. IT-00001) and QR code PDF labels
- Category-specific fields: CPU/RAM/storage (laptop, desktop), phone number (phone/tablet), ink (printer)
- Asset assignment to a person or department with full operation history
- License management (seats, expiry dates, user assignments)
- User management with department grouping
- Pagination, filtering and search on all list views
- Session flash messages and CSRF protection
- Material Design 3 interface (dark mode)
- PL/EN language switcher — preference stored in a cookie

## Requirements

- Python 3.12+
- Docker + Docker Compose (optional)

## Running locally

```bash
cd vanillatracker

python -m venv venv
source venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
# Set SECRET_KEY in .env

uvicorn app.main:app --reload
```

Open `http://localhost:8000`. On first run the setup wizard at `/setup/` will guide you through creating an admin account and choosing a tag prefix. The database and tables are created automatically on startup.

## Running with Docker

```bash
cp .env.example .env
# Fill in SECRET_KEY and database credentials

docker compose up -d
```

The image is pulled from `ghcr.io/cumill11/vanilla-tracker:latest`. The setup wizard is available at `http://localhost:8000/setup/` on first run.

## Configuration (.env)

| Variable | Description | Default |
|---|---|---|
| `SECRET_KEY` | Session secret key — change before deploying | *(none)* |
| `DATABASE_URL` | Full database URL | `sqlite:///./db.sqlite3` |
| `DB_HOST` | MySQL/MariaDB host | *(none)* |
| `DB_PORT` | MySQL/MariaDB port | `3306` |
| `DB_NAME` | Database name | `vanillatracker` |
| `DB_USER` | Database user | `root` |
| `DB_PASSWORD` | Database password | *(none)* |
| `HTTPS_ONLY` | Enforce HTTPS for the session cookie | `false` |

If `DATABASE_URL` is set, all `DB_*` variables are ignored. If neither is set, SQLite is used.

### MySQL example

```env
SECRET_KEY=random-key-min-32-chars
DATABASE_URL=mysql+pymysql://user:password@localhost:3306/vanillatracker
```

### SQLite example (dev)

```env
SECRET_KEY=random-key-min-32-chars
# DATABASE_URL not needed — SQLite is used by default
```

## Tests

```bash
# Run all tests
python -m pytest tests/

# Single file
python -m pytest tests/test_assets.py

# Stop on first failure
python -m pytest tests/ -x
```

Tests use a separate SQLite database (`test_vanillatracker.db`) that is created and deleted automatically. No running application or external database is required.

## Project structure

```
app/
├── main.py          # FastAPI app, middleware, Jinja2 filters
├── models.py        # SQLAlchemy models
├── database.py      # Engine and session
├── auth.py          # Password hashing, CSRF, authentication
├── deps.py          # FastAPI dependencies (login_required, ctx)
├── flash.py         # Session flash messages
├── i18n.py          # PL/EN translation dictionaries and context processor
├── pagination.py    # Query pagination
├── label_pdf.py     # PDF label generation with QR codes
└── routers/
    ├── setup.py     # First-run setup wizard
    ├── auth.py      # Login / logout
    ├── dashboard.py # Home page
    ├── assets.py    # Asset CRUD, assignment, labels
    ├── licenses.py  # License CRUD, user assignment
    ├── users.py     # User and password management
    └── categories.py# Categories and departments
templates/           # Jinja2 templates
static/              # CSS, JS, icons, logo
tests/               # pytest suite (69 tests)
```

## Security

- Setup wizard — the app is inaccessible until an admin account exists
- CSRF tokens verified on every POST request
- Passwords hashed with bcrypt
- Login rate limiting: 5 attempts per 5 minutes per IP
- Open redirect protection on post-login redirect
- `same_site=strict` on the session cookie
- `https_only` configurable via `HTTPS_ONLY=true`
- Jinja2 autoescape enabled
