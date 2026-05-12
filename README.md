# VanillaTracker

System ewidencji sprzętu IT zbudowany na FastAPI. Umożliwia zarządzanie sprzętem, licencjami i użytkownikami z podziałem na działy.

## Funkcje

- Kreator pierwszego uruchomienia — tworzy konto administratora i konfiguruje prefiks numerów inwentarzowych
- Ewidencja sprzętu z numerami IT-XXXXX (prefiks konfigurowalny) i kodami QR na etykietach PDF
- Pola specyficzne dla kategorii: CPU/RAM/dysk (laptop, desktop), numer telefonu (telefon/tablet), tusz (drukarka)
- Przypisywanie i zdawanie sprzętu z historią operacji
- Zarządzanie licencjami (miejsca, daty wygaśnięcia, przypisanie do użytkowników)
- Zarządzanie użytkownikami z podziałem na działy
- Paginacja, filtrowanie i wyszukiwanie na wszystkich listach
- Sesyjne komunikaty flash i ochrona CSRF
- Interfejs w Material Design 3 (dark mode)

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
