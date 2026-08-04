/** Stronicowanie — port `pagination.py` na zapytania D1. */
import type { D1Database } from '@cloudflare/workers-types';

const PER_PAGE = 25;

export type Page<T> = {
  items: T[];
  total: number;
  page: number;
  perPage: number;
  numPages: number;
  hasPrev: boolean;
  hasNext: boolean;
};

export type PageQuery = {
  /** Lista kolumn bez `SELECT`. */
  columns: string;
  /** Tabela wraz ze złączeniami, bez `FROM`. */
  from: string;
  /** Warunek wraz ze słowem `WHERE` albo pusty napis. */
  where?: string;
  /** Sortowanie bez `ORDER BY`. */
  orderBy: string;
  args?: unknown[];
  page: number;
  perPage?: number;
};

/**
 * Zwraca stronę wyników wraz z łączną liczbą wierszy.
 *
 * Liczbę wszystkich pasujących wierszy bierzemy z funkcji okna `COUNT(*) OVER ()`,
 * którą SQLite liczy przed zastosowaniem `LIMIT`. Dzięki temu wystarcza jedno
 * zapytanie zamiast osobnego `SELECT COUNT(*)`, a warunek `WHERE` jest zapisany
 * w jednym miejscu — wcześniej każda lista powtarzała go dwa razy.
 */
export async function paginate<T>(db: D1Database, query: PageQuery): Promise<Page<T>> {
  const { columns, from, where = '', orderBy, args = [], page, perPage = PER_PAGE } = query;

  const fetchPage = async (current: number) => {
    const { results } = await db
      .prepare(
        `SELECT ${columns}, COUNT(*) OVER () AS _total
           FROM ${from}
           ${where}
          ORDER BY ${orderBy}
          LIMIT ? OFFSET ?`,
      )
      .bind(...args, perPage, (current - 1) * perPage)
      .all<T & { _total: number }>();
    return results ?? [];
  };

  let current = Math.max(1, Number.isFinite(page) ? page : 1);
  let rows = await fetchPage(current);

  // Pusta strona przy numerze spoza zakresu: cofamy się na ostatnią istniejącą,
  // tak jak robił to `paginate` z wersji Flask. Zdarza się tylko przy ręcznie
  // wpisanym adresie, więc dodatkowe zapytanie nie obciąża normalnego ruchu.
  if (rows.length === 0 && current > 1) {
    const countRow = await db
      .prepare(`SELECT COUNT(*) AS n FROM ${from} ${where}`)
      .bind(...args)
      .first<{ n: number }>();
    const total = countRow?.n ?? 0;
    if (total > 0) {
      current = Math.ceil(total / perPage);
      rows = await fetchPage(current);
    }
  }

  const total = rows[0]?._total ?? 0;
  const numPages = Math.max(1, Math.ceil(total / perPage));

  return {
    items: rows as unknown as T[],
    total,
    page: current,
    perPage,
    numPages,
    hasPrev: current > 1,
    hasNext: current < numPages,
  };
}

export function parsePage(value: string | null): number {
  const n = Number.parseInt(value ?? '1', 10);
  return Number.isInteger(n) && n > 0 ? n : 1;
}

/** Buduje query string dla linków stronicowania, pomijając puste filtry. */
export function pageHref(filters: Record<string, string | number>, page: number): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== '' && value !== undefined && value !== null) params.set(key, String(value));
  }
  params.set('page', String(page));
  return `?${params.toString()}`;
}
