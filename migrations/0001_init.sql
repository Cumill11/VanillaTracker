-- VanillaTracker — schemat początkowy dla Cloudflare D1.
--
-- Różnice względem wersji Flask/SQLAlchemy:
--   * brak kolumn logowania w `users` (password_hash, is_superuser, last_login)
--     — logować może się wyłącznie administrator, konfigurowany przez sekrety Workera;
--   * `user_profiles` scalone z `users` (department_id, phone, position);
--   * brak tabeli `settings` — prefiks tagów pochodzi ze zmiennej TAG_PREFIX;
--   * daty i znaczniki czasu trzymane jako TEXT w ISO-8601 (porównywalne leksykalnie),
--     kwoty jako TEXT (dokładność dziesiętna, odpowiednik NUMERIC(10,2)).

CREATE TABLE categories (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  name        TEXT NOT NULL,
  slug        TEXT NOT NULL UNIQUE,
  description TEXT NOT NULL DEFAULT ''
);

CREATE TABLE departments (
  id   INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL
);

CREATE TABLE users (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  first_name    TEXT NOT NULL DEFAULT '',
  last_name     TEXT NOT NULL DEFAULT '',
  email         TEXT NOT NULL DEFAULT '',
  phone         TEXT NOT NULL DEFAULT '',
  position      TEXT NOT NULL DEFAULT '',
  department_id INTEGER REFERENCES departments(id) ON DELETE SET NULL,
  created_at    TEXT NOT NULL
);
CREATE INDEX idx_users_name ON users(last_name, first_name);
CREATE INDEX idx_users_department ON users(department_id);

CREATE TABLE assets (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  asset_tag       TEXT NOT NULL UNIQUE,
  tag_number      INTEGER NOT NULL UNIQUE,
  name            TEXT NOT NULL,
  category_id     INTEGER REFERENCES categories(id) ON DELETE SET NULL,
  manufacturer    TEXT NOT NULL DEFAULT '',
  model_name      TEXT NOT NULL DEFAULT '',
  serial_number   TEXT,
  purchase_date   TEXT,
  purchase_price  TEXT,
  warranty_expiry TEXT,
  status          TEXT NOT NULL DEFAULT 'available',
  assigned_to_id  INTEGER REFERENCES users(id) ON DELETE SET NULL,
  assigned_date   TEXT,
  department_id   INTEGER REFERENCES departments(id) ON DELETE SET NULL,
  location        TEXT NOT NULL DEFAULT '',
  notes           TEXT NOT NULL DEFAULT '',
  cpu             TEXT NOT NULL DEFAULT '',
  ram             TEXT NOT NULL DEFAULT '',
  storage         TEXT NOT NULL DEFAULT '',
  phone_number    TEXT NOT NULL DEFAULT '',
  ink_type        TEXT NOT NULL DEFAULT '',
  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL
);
CREATE INDEX idx_assets_status ON assets(status);
CREATE INDEX idx_assets_category ON assets(category_id);
CREATE INDEX idx_assets_assigned_to ON assets(assigned_to_id);
CREATE INDEX idx_assets_warranty ON assets(warranty_expiry);

CREATE TABLE licenses (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  asset_tag      TEXT NOT NULL UNIQUE,
  tag_number     INTEGER NOT NULL UNIQUE,
  name           TEXT NOT NULL,
  vendor         TEXT NOT NULL DEFAULT '',
  license_key    TEXT NOT NULL DEFAULT '',
  seats          INTEGER NOT NULL DEFAULT 1,
  purchase_date  TEXT,
  expiry_date    TEXT,
  purchase_price TEXT,
  status         TEXT NOT NULL DEFAULT 'active',
  notes          TEXT NOT NULL DEFAULT '',
  created_at     TEXT NOT NULL,
  updated_at     TEXT NOT NULL
);
CREATE INDEX idx_licenses_status ON licenses(status);
CREATE INDEX idx_licenses_expiry ON licenses(expiry_date);

CREATE TABLE license_users (
  license_id INTEGER NOT NULL REFERENCES licenses(id) ON DELETE CASCADE,
  user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  PRIMARY KEY (license_id, user_id)
);
CREATE INDEX idx_license_users_user ON license_users(user_id);

CREATE TABLE asset_history (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  asset_id   INTEGER REFERENCES assets(id) ON DELETE CASCADE,
  license_id INTEGER REFERENCES licenses(id) ON DELETE CASCADE,
  action     TEXT NOT NULL,
  user_id    INTEGER REFERENCES users(id) ON DELETE SET NULL,
  note       TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
);
CREATE INDEX idx_history_asset ON asset_history(asset_id, created_at);
CREATE INDEX idx_history_license ON asset_history(license_id, created_at);
CREATE INDEX idx_history_user ON asset_history(user_id, created_at);
CREATE INDEX idx_history_created ON asset_history(created_at);

-- Licznik numerów inwentarzowych (zawsze dokładnie jeden wiersz, id = 1).
CREATE TABLE asset_counter (
  id          INTEGER PRIMARY KEY,
  last_number INTEGER NOT NULL DEFAULT 0
);

-- Numery zwolnione przez usunięty sprzęt/licencje — używane ponownie przed
-- zwiększeniem licznika.
CREATE TABLE tag_pool (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  tag_number INTEGER NOT NULL UNIQUE
);

-- Limit prób logowania (5 prób / 5 minut na adres IP).
CREATE TABLE login_attempts (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  ip           TEXT NOT NULL,
  attempted_at TEXT NOT NULL
);
CREATE INDEX idx_login_attempts ON login_attempts(ip, attempted_at);

-- ── Dane startowe ───────────────────────────────────────────────────────────
INSERT INTO asset_counter (id, last_number) VALUES (1, 0);

INSERT INTO categories (name, slug) VALUES
  ('Laptop',               'laptop'),
  ('Komputer stacjonarny', 'desktop'),
  ('Monitor',              'monitor'),
  ('Telefon',              'phone'),
  ('Tablet',               'tablet'),
  ('Drukarka',             'printer'),
  ('Sprzęt sieciowy',      'network'),
  ('Peryferia',            'peripheral'),
  ('Licencja',             'license'),
  ('Inne',                 'other');
