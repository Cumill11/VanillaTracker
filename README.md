# VanillaTracker

[Polski](#polski) · [English](#english)

---

## Polski

VanillaTracker to lekka aplikacja webowa do ewidencji sprzętu IT i licencji
oprogramowania — inwentarz sprzętu, stanowiska licencyjne, pracownicy i działy,
historia przypisań oraz etykiety QR do druku. Napisana we Flasku, działa zarówno
na SQLite lokalnie, jak i na MariaDB/MySQL w środowisku produkcyjnym.

### Funkcje

- **Sprzęt** — pełny inwentarz z kategoriami, statusem, gwarancją, danymi zakupu
  i specyfikacją (CPU / RAM / dysk).
- **Licencje** — licencje oprogramowania ze stanowiskami, terminami ważności
  i przypisaniem do użytkowników.
- **Ludzie i działy** — przypisywanie sprzętu do pracowników lub całych działów.
- **Historia** — każde przypisanie, zwrot, zmiana statusu i notatka są rejestrowane.
- **Etykiety QR** — generowanie etykiet PDF do druku (pojedynczo lub zbiorczo).
- **Pulpit** — liczniki, kończące się gwarancje/licencje, ostatnia aktywność.
- **Dwujęzyczny interfejs** — polski i angielski, przełączany w locie.
- **Bezpieczeństwo** — hasła bcrypt, ochrona CSRF, limit prób logowania,
  zarządzanie użytkownikami tylko dla administratora.

### Stos technologiczny

- Python 3.14 · Flask · SQLAlchemy
- MariaDB / MySQL (produkcja) lub SQLite (tryb lokalny)
- gunicorn (serwer WSGI) · Docker

### Struktura projektu

```
vanillatrackerFlask/
├── flask_app/
│   ├── app.py            # trasy i logika aplikacji
│   ├── database.py       # połączenie z bazą danych
│   ├── models.py         # modele SQLAlchemy
│   ├── i18n.py           # tłumaczenia PL / EN
│   ├── label_pdf.py      # generowanie etykiet QR (PDF)
│   ├── pagination.py     # pomocnik paginacji
│   ├── requirements.txt
│   ├── static/
│   └── templates/
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

### Konfiguracja

Aplikacja czyta konfigurację z pliku `.env` w katalogu głównym projektu.
Skopiuj szablon i uzupełnij wartości:

```bash
cp .env.example .env
```

| Zmienna | Opis | Domyślnie |
|---|---|---|
| `SECRET_KEY` | Klucz sesji Flask — na produkcji wygeneruj losowy | *(niebezpieczna wartość domyślna)* |
| `HTTPS_ONLY` | `true` oznacza cookie sesji jako `Secure` (przy HTTPS) | `false` |
| `FLASK_DEBUG` | Tryb debug serwera dev — **nigdy `true` na produkcji** | `false` |
| `FLASK_HOST` / `FLASK_PORT` | Adres nasłuchu dla `python app.py` | `0.0.0.0` / `8000` |
| `DATABASE_URL` | Pełny URL bazy danych (ma pierwszeństwo nad `DB_*`) | — |
| `DB_HOST` / `DB_PORT` / `DB_NAME` / `DB_USER` / `DB_PASSWORD` | Parametry połączenia MariaDB/MySQL | — |

Jeśli nie ustawiono ani `DATABASE_URL`, ani `DB_HOST`, używana jest lokalna
baza SQLite.

Wygenerowanie klucza sesji:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### Uruchomienie lokalne

```bash
cd flask_app
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Aplikacja jest dostępna pod adresem <http://localhost:8000>.

### Uruchomienie w Dockerze

Obraz Dockera uruchamia aplikację pod gunicornem (produkcyjny serwer WSGI).

```bash
# Zbuduj obraz
docker build -t vanillatracker:latest .

# Uruchom gotowy obraz
docker compose up -d
```

`docker-compose.yml` przekazuje konfigurację z pliku `.env` i udostępnia port
`8000` (port na hoście można zmienić zmienną `HOST_PORT`).

### Pierwsze uruchomienie

Przy pierwszym uruchomieniu aplikacja przekierowuje na `/setup/`, gdzie tworzysz
konto administratora i wybierasz prefiks tagów sprzętu (np. `IT`, `BS`).
Następnie zaloguj się przez `/login/`.

### Baza danych

Tabele tworzone są automatycznie przy starcie (`create_all`) — nie trzeba
ręcznie wykonywać migracji. Istniejąca baza z wersji FastAPI tej aplikacji
jest w pełni zgodna.

---

## English

VanillaTracker is a lightweight web application for tracking IT assets and software
licenses — hardware inventory, license seats, people and departments, assignment
history, and printable QR labels. Built with Flask, it runs equally well on SQLite
for local use or MariaDB/MySQL in production.

### Features

- **Assets** — full hardware inventory with categories, status, warranty, purchase
  data and specs (CPU / RAM / storage).
- **Licenses** — software licenses with seats, expiry tracking and per-user assignment.
- **People & departments** — assign assets to employees or whole departments.
- **History** — every assignment, return, status change and note is logged.
- **QR labels** — generate printable PDF labels (single or bulk) for asset tags.
- **Dashboard** — counts, expiring warranties/licenses, recent activity.
- **Bilingual UI** — Polish and English, switchable on the fly.
- **Security** — bcrypt passwords, CSRF protection, login rate limiting,
  admin-only user management.

### Tech stack

- Python 3.14 · Flask · SQLAlchemy
- MariaDB / MySQL (production) or SQLite (local fallback)
- gunicorn (WSGI server) · Docker

### Project layout

```
vanillatrackerFlask/
├── flask_app/
│   ├── app.py            # routes and application logic
│   ├── database.py       # database connection
│   ├── models.py         # SQLAlchemy models
│   ├── i18n.py           # PL / EN translations
│   ├── label_pdf.py      # QR label PDF generation
│   ├── pagination.py     # pagination helper
│   ├── requirements.txt
│   ├── static/
│   └── templates/
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

### Configuration

The application reads configuration from a `.env` file in the project root.
Copy the template and adjust the values:

```bash
cp .env.example .env
```

| Variable | Description | Default |
|---|---|---|
| `SECRET_KEY` | Flask session key — generate a random one for production | *(insecure default)* |
| `HTTPS_ONLY` | `true` marks session cookies as `Secure` (use behind HTTPS) | `false` |
| `FLASK_DEBUG` | Dev server debug mode — **never `true` in production** | `false` |
| `FLASK_HOST` / `FLASK_PORT` | Bind address for `python app.py` | `0.0.0.0` / `8000` |
| `DATABASE_URL` | Full database URL (takes precedence over `DB_*`) | — |
| `DB_HOST` / `DB_PORT` / `DB_NAME` / `DB_USER` / `DB_PASSWORD` | MariaDB/MySQL connection parameters | — |

If neither `DATABASE_URL` nor `DB_HOST` is set, a local SQLite database is used.

Generate a secret key:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### Running locally

```bash
cd flask_app
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

The app is available at <http://localhost:8000>.

### Running with Docker

The Docker image runs the app under gunicorn (production WSGI server).

```bash
# Build the image
docker build -t vanillatracker:latest .

# Run the pre-built image
docker compose up -d
```

`docker-compose.yml` passes configuration from `.env` and exposes port `8000`
(override the host port with the `HOST_PORT` variable).

### First run

On first launch the app redirects to `/setup/`, where you create the
administrator account and choose the asset tag prefix (e.g. `IT`, `BS`).
After that, log in at `/login/`.

### Database

Tables are created automatically on startup (`create_all`) — no manual
migration step is required. An existing database from the FastAPI version of
this app is fully compatible.

---

Autor / Author: Kamil Kowalczyk
