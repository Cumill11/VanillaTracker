# VanillaTracker

System ewidencji sprzętu IT zbudowany na FastAPI. Umożliwia zarządzanie sprzętem, licencjami i użytkownikami z podziałem na działy.

## Funkcje

- Ewidencja sprzętu z numerami BS-XXXXX i kodami QR na etykietach PDF
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
cd assets-fastapi

# Utwórz środowisko wirtualne
python -m venv venv
source venv/bin/activate

# Zainstaluj zależności
pip install -r requirements.txt

# Utwórz plik .env
cp .env.example .env
# Uzupełnij SECRET_KEY w .env

# Zainicjuj bazę danych (SQLite domyślnie)
python init_db.py

# Uruchom serwer
uvicorn app.main:app --reload
```

Aplikacja dostępna pod `http://localhost:8000`. Przy pierwszym uruchomieniu kreator na `/setup/` poprowadzi przez tworzenie konta administratora.

## Uruchomienie przez Docker

```bash
# Uzupełnij .env (skopiuj z .env.example i zmień hasła)
cp .env.example .env

# Zbuduj i uruchom
docker compose up -d --build

# Zainicjuj bazę danych (tylko przy pierwszym uruchomieniu)
docker compose exec web python init_db.py
```

## Konfiguracja (.env)

| Zmienna | Opis | Domyślnie |
|---|---|---|
| `SECRET_KEY` | Klucz sesji — zmień przed wdrożeniem | *(brak)* |
| `DATABASE_URL` | URL bazy danych | `sqlite:///./db.sqlite3` |
| `DB_NAME` | Nazwa bazy MySQL (Docker) | `assets` |
| `DB_USER` | Użytkownik MySQL (Docker) | `assets` |
| `DB_PASSWORD` | Hasło użytkownika MySQL (Docker) | *(brak)* |
| `DB_ROOT_PASSWORD` | Hasło root MySQL (Docker) | *(brak)* |

### Połączenie z MySQL (lokalnie)

```bash
pip install pymysql
# W .env:
DATABASE_URL=mysql+pymysql://user:password@localhost:3306/assets
```

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
    ├── auth.py      # Logowanie / wylogowanie
    ├── dashboard.py # Strona główna
    ├── assets.py    # CRUD sprzętu, przypisanie, etykiety
    ├── licenses.py  # CRUD licencji, przypisanie użytkowników
    ├── users.py     # CRUD użytkowników
    └── categories.py# Kategorie i działy
templates/           # Szablony Jinja2
static/              # CSS, JS, ikony
```

## Bezpieczeństwo

- Tokeny CSRF weryfikowane na każdym żądaniu POST
- Hasła haszowane bcryptem
- Rate limiting logowania: 5 prób / 5 minut per IP
- Ochrona przed open redirect przy przekierowaniu po logowaniu
- `same_site=strict` na ciasteczku sesji
- Autoescape włączony w szablonach Jinja2
