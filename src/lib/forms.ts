/** Parsowanie i walidacja danych z formularzy - port pomocników z `app.py`. */

export type Errors = Record<string, string[]>;

/** Wartość pola formularza jako string (FormData zwraca też File). */
export function field(form: FormData, name: string): string {
  const value = form.get(name);
  return typeof value === 'string' ? value : '';
}

export function fieldList(form: FormData, name: string): string[] {
  return form.getAll(name).filter((v): v is string => typeof v === 'string');
}

/** `YYYY-MM-DD` albo null. Odrzuca daty niepoprawne kalendarzowo (np. 2026-02-30). */
export function parseDate(value: string): string | null {
  const trimmed = value.trim();
  if (!/^\d{4}-\d{2}-\d{2}$/.test(trimmed)) return null;
  const date = new Date(`${trimmed}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return null;
  return date.toISOString().slice(0, 10) === trimmed ? trimmed : null;
}

/**
 * Kwota jako tekst z dwoma miejscami po przecinku (odpowiednik NUMERIC(10,2)).
 * Akceptuje przecinek dziesiętny, tak jak wersja Flask.
 */
export function parseDecimal(value: string): string | null {
  const normalized = value.trim().replace(',', '.');
  if (!normalized) return null;
  if (!/^-?\d{1,8}(\.\d+)?$/.test(normalized)) return null;
  const num = Number.parseFloat(normalized);
  if (!Number.isFinite(num)) return null;
  return num.toFixed(2);
}

export function parseInteger(value: string | null | undefined): number | null {
  if (value === null || value === undefined) return null;
  const trimmed = value.trim();
  if (!/^-?\d+$/.test(trimmed)) return null;
  const n = Number.parseInt(trimmed, 10);
  return Number.isSafeInteger(n) ? n : null;
}

/** Dodatnia liczba całkowita z segmentu ścieżki (`/assets/12/`). */
export function parseId(value: string | undefined): number | null {
  const n = parseInteger(value);
  return n !== null && n > 0 ? n : null;
}

export function parseSeats(value: string): number {
  const n = parseInteger(value);
  return n !== null && n > 0 ? n : 1;
}

/** Wzorzec do LIKE - escapujemy `%`, `_` i `\` (klauzula ESCAPE '\'). */
export function likePattern(query: string): string {
  return `%${query.replace(/[\\%_]/g, (ch) => `\\${ch}`)}%`;
}
