/**
 * INSERT i UPDATE budowane z mapy `kolumna → wartość`.
 *
 * Ręcznie pisane zapytania wymagały trzymania w zgodzie listy kolumn i listy
 * wiązań — przestawienie jednego pola cicho zapisywało dane w złej kolumnie.
 * Tutaj oba wynikają z tego samego obiektu.
 *
 * Nazwy tabel i kolumn pochodzą wyłącznie z literałów w kodzie (nigdy z danych
 * użytkownika), a wartości idą przez parametry — SQL injection nie wchodzi w grę.
 */
import type { D1Database } from '@cloudflare/workers-types';

export type Columns = Record<string, unknown>;

/** Wstawia wiersz i zwraca jego `id` (null, gdy baza nic nie zwróciła). */
export async function insertRow(
  db: D1Database,
  table: string,
  values: Columns,
): Promise<number | null> {
  const names = Object.keys(values);
  const row = await db
    .prepare(
      `INSERT INTO ${table} (${names.join(', ')})
       VALUES (${names.map(() => '?').join(', ')})
       RETURNING id`,
    )
    .bind(...Object.values(values))
    .first<{ id: number }>();
  return row?.id ?? null;
}

export async function updateRow(
  db: D1Database,
  table: string,
  values: Columns,
  id: number,
): Promise<void> {
  const assignments = Object.keys(values)
    .map((name) => `${name} = ?`)
    .join(', ');
  await db
    .prepare(`UPDATE ${table} SET ${assignments} WHERE id = ?`)
    .bind(...Object.values(values), id)
    .run();
}
