/**
 * Filtry listy sprzętu - wspólne dla widoku HTML i eksportu CSV, żeby
 * „Eksport" oddawał dokładnie to, co widać na ekranie.
 */
import { likePattern } from './forms';

/** Biała lista sortowań - wartość trafia wprost do `ORDER BY`. */
const SORTS: Record<string, string> = {
  tag_number: 'a.tag_number',
  '-tag_number': 'a.tag_number DESC',
  name: 'a.manufacturer, a.model_name',
  '-name': 'a.manufacturer DESC, a.model_name DESC',
  status: 'a.status',
  category__name: 'c.name, a.tag_number',
};

/** Złączenia potrzebne zarówno liście, jak i eksportowi. */
export const ASSET_FROM = `assets a
             LEFT JOIN categories c   ON c.id = a.category_id
             LEFT JOIN users u        ON u.id = a.assigned_to_id
             LEFT JOIN departments d  ON d.id = a.department_id`;

type AssetFilters = {
  q: string;
  category: string;
  status: string;
  sort: string;
  orderBy: string;
  where: string;
  args: unknown[];
};

export function assetFilters(params: URLSearchParams): AssetFilters {
  const q = params.get('q') ?? '';
  const category = params.get('category') ?? '';
  const status = params.get('status') ?? '';
  const sort = params.get('sort') ?? 'tag_number';

  const where: string[] = [];
  const args: unknown[] = [];

  if (q) {
    // Parametr powtórzony dla każdej kolumny - D1 nie lubi mieszania
    // numerowanych (?1) i anonimowych (?) placeholderów w jednym zapytaniu.
    const columns = [
      'a.asset_tag',
      'a.serial_number',
      // Sklejenie, bo szukana fraza bywa rozłożona na dwie kolumny („HP EliteBook").
      "(a.manufacturer || ' ' || a.model_name)",
    ];
    where.push(`(${columns.map((c) => `${c} LIKE ? ESCAPE '\\'`).join(' OR ')})`);
    for (let i = 0; i < columns.length; i++) args.push(likePattern(q));
  }
  if (category) {
    where.push('a.category_id = ?');
    args.push(category);
  }
  if (status) {
    where.push('a.status = ?');
    args.push(status);
  }

  return {
    q,
    category,
    status,
    sort,
    orderBy: SORTS[sort] ?? SORTS.tag_number,
    where: where.length ? `WHERE ${where.join(' AND ')}` : '',
    args,
  };
}
