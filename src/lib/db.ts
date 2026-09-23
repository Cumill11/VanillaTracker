/** Typy wierszy D1 i wspólne operacje na bazie. */
import type { D1Database } from '@cloudflare/workers-types';

// ── Stałe domenowe (odpowiedniki STATUS_CHOICES z models.py) ────────────────

export const ASSET_STATUS = {
  AVAILABLE: 'available',
  ASSIGNED: 'assigned',
  MAINTENANCE: 'maintenance',
  RETIRED: 'retired',
} as const;

export const ASSET_STATUS_VALUES = [
  ASSET_STATUS.AVAILABLE,
  ASSET_STATUS.ASSIGNED,
  ASSET_STATUS.MAINTENANCE,
  ASSET_STATUS.RETIRED,
] as const;

export const LICENSE_STATUS = {
  ACTIVE: 'active',
  EXPIRED: 'expired',
  INACTIVE: 'inactive',
} as const;

export const LICENSE_STATUS_VALUES = [
  LICENSE_STATUS.ACTIVE,
  LICENSE_STATUS.EXPIRED,
  LICENSE_STATUS.INACTIVE,
] as const;

/** Statusy, które można ustawić ręcznie — „expired" wynika z daty wygaśnięcia. */
export const LICENSE_MANUAL_STATUS_VALUES = [
  LICENSE_STATUS.ACTIVE,
  LICENSE_STATUS.INACTIVE,
] as const;

export const HISTORY_ACTION = {
  ASSIGN: 'assign',
  RETURN: 'return',
  MAINTENANCE: 'maintenance',
  NOTE: 'note',
  STATUS: 'status',
  ASSIGN_DEPT: 'assign_dept',
} as const;

// ── Wiersze ─────────────────────────────────────────────────────────────────

export type CategoryRow = {
  id: number;
  name: string;
  slug: string;
};

export type DepartmentRow = {
  id: number;
  name: string;
};

export type UserRow = {
  id: number;
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  position: string;
  department_id: number | null;
  created_at: string;
};

export type AssetRow = {
  id: number;
  asset_tag: string;
  tag_number: number;
  category_id: number | null;
  manufacturer: string;
  model_name: string;
  serial_number: string | null;
  purchase_date: string | null;
  purchase_price: string | null;
  warranty_expiry: string | null;
  status: string;
  assigned_to_id: number | null;
  assigned_date: string | null;
  department_id: number | null;
  notes: string;
  cpu: string;
  ram: string;
  storage: string;
  phone_number: string;
  ink_type: string;
  created_at: string;
  updated_at: string;
};

export type LicenseRow = {
  id: number;
  asset_tag: string;
  tag_number: number;
  name: string;
  vendor: string;
  license_key: string;
  seats: number;
  purchase_date: string | null;
  expiry_date: string | null;
  purchase_price: string | null;
  status: string;
  notes: string;
  created_at: string;
  updated_at: string;
};

type HistoryRow = {
  id: number;
  asset_id: number | null;
  license_id: number | null;
  action: string;
  user_id: number | null;
  note: string;
  created_at: string;
};

/** Wiersz historii wzbogacony o dane powiązanych obiektów (JOIN). */
export type HistoryWithRefs = HistoryRow & {
  asset_tag: string | null;
  license_tag: string | null;
  user_first_name: string | null;
  user_last_name: string | null;
};

// ── Pomocnicze ──────────────────────────────────────────────────────────────

export function nowIso(): string {
  return new Date().toISOString();
}

export function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export function addDaysIso(days: number): string {
  return new Date(Date.now() + days * 86_400_000).toISOString().slice(0, 10);
}

type NamedPerson = { first_name: string; last_name: string };

export function fullName(user: NamedPerson): string {
  return `${user.first_name} ${user.last_name}`.trim() || '—';
}

/**
 * Nazwa sprzętu — składana z producenta i modelu.
 *
 * Sprzęt nie ma osobnego pola z nazwą: było ono kopią tych dwóch wartości,
 * więc rozjeżdżało się przy edycji i dublowało w listach.
 */
export function assetName(asset: { manufacturer: string; model_name: string }): string {
  return `${asset.manufacturer} ${asset.model_name}`.trim() || '—';
}

export function initials(user: NamedPerson): string {
  const name = fullName(user);
  return name === '—' ? '?' : name[0]!.toUpperCase();
}

/**
 * Rezerwuje kolejny numer inwentarzowy.
 *
 * Najpierw sięga po numer zwolniony przez usunięty obiekt (tag_pool), a dopiero
 * potem zwiększa licznik. Oba zapytania są atomowe w obrębie pojedynczego
 * `UPDATE ... RETURNING` / `DELETE ... RETURNING` — D1 nie ma `SELECT FOR UPDATE`,
 * którego używała wersja SQLAlchemy.
 */
export async function nextTag(
  db: D1Database,
  prefix: string,
): Promise<{ number: number; tag: string }> {
  const pooled = await db
    .prepare(
      `DELETE FROM tag_pool
        WHERE id = (SELECT id FROM tag_pool ORDER BY tag_number LIMIT 1)
        RETURNING tag_number`,
    )
    .first<{ tag_number: number }>();

  if (pooled) {
    return { number: pooled.tag_number, tag: formatTag(prefix, pooled.tag_number) };
  }

  const counter = await db
    .prepare(
      `UPDATE asset_counter SET last_number = last_number + 1
        WHERE id = 1
        RETURNING last_number`,
    )
    .first<{ last_number: number }>();

  if (!counter) throw new Error('Brak wiersza asset_counter (id=1) — uruchom migracje D1.');
  return { number: counter.last_number, tag: formatTag(prefix, counter.last_number) };
}

function formatTag(prefix: string, number: number): string {
  return `${prefix}-${String(number).padStart(5, '0')}`;
}

/** Usuwa sprzęt lub licencję i zwraca jego numer inwentarzowy do puli. */
export async function deleteWithTagRelease(
  db: D1Database,
  table: 'assets' | 'licenses',
  id: number,
  tagNumber: number,
): Promise<void> {
  await db.batch([
    db.prepare('INSERT OR IGNORE INTO tag_pool (tag_number) VALUES (?)').bind(tagNumber),
    db.prepare(`DELETE FROM ${table} WHERE id = ?`).bind(id),
  ]);
}

/** Prefiks tagów ze zmiennej środowiskowej; 2–4 wielkie litery, domyślnie „BS". */
export function tagPrefix(env: { TAG_PREFIX?: string }): string {
  const raw = (env.TAG_PREFIX ?? '').trim().toUpperCase();
  return /^[A-Z]{2,4}$/.test(raw) ? raw : 'BS';
}

export function addHistory(
  db: D1Database,
  entry: {
    asset_id?: number | null;
    license_id?: number | null;
    action: string;
    user_id?: number | null;
    note?: string;
  },
) {
  return db
    .prepare(
      `INSERT INTO asset_history (asset_id, license_id, action, user_id, note, created_at)
       VALUES (?, ?, ?, ?, ?, ?)`,
    )
    .bind(
      entry.asset_id ?? null,
      entry.license_id ?? null,
      entry.action,
      entry.user_id ?? null,
      entry.note ?? '',
      nowIso(),
    );
}

/**
 * Ten sam status liczony w SQL (licencja pod aliasem `l`). Zapisany `status`
 * nie zmienia się sam, gdy mija data wygaśnięcia — bez tego licencja po
 * terminie dalej widniałaby na listach i w filtrze jako „active".
 */
export const LICENSE_STATUS_SQL = `CASE WHEN l.expiry_date < date('now') THEN '${LICENSE_STATUS.EXPIRED}' ELSE l.status END`;

/**
 * Status licencji: „expired" wynika wprost z daty wygaśnięcia i ma pierwszeństwo
 * przed wyborem użytkownika (port `_effective_status`).
 */
export function effectiveLicenseStatus(expiryDate: string | null, manualStatus: string): string {
  if (expiryDate && expiryDate < todayIso()) return LICENSE_STATUS.EXPIRED;
  if (manualStatus === LICENSE_STATUS.ACTIVE || manualStatus === LICENSE_STATUS.INACTIVE) {
    return manualStatus;
  }
  return LICENSE_STATUS.ACTIVE;
}
