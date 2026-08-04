/** Filtry prezentacyjne — port filtrów Jinja z `app.py`. */

const DASH = '—';

/** Strefa dla znaczników czasu; daty kalendarzowe formatowane są bez konwersji. */
const TIMEZONE = 'Europe/Warsaw';

const CATEGORY_ICONS: Record<string, string> = {
  laptop: 'laptop',
  desktop: 'desktop_windows',
  monitor: 'monitor',
  phone: 'smartphone',
  tablet: 'tablet',
  printer: 'print',
  network: 'router',
  peripheral: 'keyboard',
  license: 'key',
  other: 'devices_other',
};

export function categoryIcon(slug: string | null | undefined): string {
  return (slug && CATEGORY_ICONS[slug]) || 'devices_other';
}

const STATUS_COLORS: Record<string, string> = {
  available: '#4CAF50',
  assigned: '#2196F3',
  maintenance: '#FF9800',
  retired: '#F44336',
  active: '#4CAF50',
  expired: '#F44336',
  inactive: '#9E9E9E',
};

export function statusColor(status: string): string {
  return STATUS_COLORS[status] ?? '#9E9E9E';
}

/** `YYYY-MM-DD` → `DD.MM.YYYY`. Data kalendarzowa, więc bez strefy czasowej. */
export function formatDate(value: string | null | undefined): string {
  if (!value) return DASH;
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  if (!m) return value;
  return `${m[3]}.${m[2]}.${m[1]}`;
}

/** Znacznik ISO → `DD.MM.YYYY HH:MM` w podanej strefie. */
export function formatDateTime(value: string | null | undefined): string {
  if (!value) return DASH;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;

  const parts = new Intl.DateTimeFormat('pl-PL', {
    timeZone: TIMEZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).formatToParts(date);

  const get = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((p) => p.type === type)?.value ?? '00';

  return `${get('day')}.${get('month')}.${get('year')} ${get('hour')}:${get('minute')}`;
}

/** Cena trzymana jest jako TEXT — pokazujemy ją z dopiskiem waluty. */
export function formatPrice(value: string | null | undefined): string | null {
  if (!value) return null;
  return `${value} PLN`;
}

/** Wypełnienie paska stanowisk licencji (0–100). */
export function seatsPercent(used: number, seats: number): number {
  if (!seats) return 0;
  return Math.min(100, Math.trunc((used / seats) * 100));
}

export function seatsBarClass(percent: number): string {
  if (percent >= 100) return 'full';
  if (percent >= 80) return 'warn';
  return '';
}
