/**
 * Uwierzytelnianie administratora.
 *
 * W tej wersji nie ma kont użytkowników — logować może się wyłącznie jeden
 * administrator, którego login i hasło pochodzą z sekretów Workera
 * (ADMIN_USERNAME, ADMIN_PASSWORD). Osoby w tabeli `users` są wyłącznie
 * odbiorcami sprzętu i licencji.
 */
import type { D1Database } from '@cloudflare/workers-types';
import { secretEquals } from './crypto';
import { nowIso } from './db';

const RATE_LIMIT = 5;
const RATE_WINDOW_SECONDS = 300;

type AdminSecrets = { ADMIN_USERNAME?: string; ADMIN_PASSWORD?: string };

/** Ścieżki dostępne bez zalogowania. */
export function isPublicPath(pathname: string): boolean {
  return (
    pathname === '/login' ||
    pathname.startsWith('/login/') ||
    pathname.startsWith('/img/') ||
    pathname.startsWith('/_astro/') ||
    pathname === '/favicon.ico'
  );
}

export function adminConfigured(env: AdminSecrets): boolean {
  return Boolean(env.ADMIN_USERNAME && env.ADMIN_PASSWORD);
}

export async function authenticateAdmin(
  env: AdminSecrets,
  username: string,
  password: string,
): Promise<boolean> {
  if (!adminConfigured(env)) return false;

  // Oba porównania wykonujemy zawsze (bez `&&` skracającego obliczenia) —
  // inaczej czas odpowiedzi zdradzałby, czy sam login jest poprawny.
  const [nameMatches, passwordMatches] = await Promise.all([
    secretEquals(username, env.ADMIN_USERNAME!),
    secretEquals(password, env.ADMIN_PASSWORD!),
  ]);
  return nameMatches && passwordMatches;
}

/**
 * Limit prób logowania: 5 na 5 minut z jednego IP (port `_check_rate_limit`).
 * Zwraca false, gdy limit został przekroczony.
 */
export async function checkRateLimit(db: D1Database, ip: string): Promise<boolean> {
  const cutoff = new Date(Date.now() - RATE_WINDOW_SECONDS * 1000).toISOString();

  // Sprzątanie starych wpisów i zliczanie bieżących nie zależą od siebie —
  // oba filtrują po tej samej granicy czasu, więc idą jednym okrążeniem.
  const [, countResult] = await db.batch([
    db.prepare('DELETE FROM login_attempts WHERE attempted_at < ?').bind(cutoff),
    db
      .prepare('SELECT COUNT(*) AS n FROM login_attempts WHERE ip = ? AND attempted_at >= ?')
      .bind(ip, cutoff),
  ]);

  const attempts = (countResult.results as { n: number }[])[0]?.n ?? 0;
  if (attempts >= RATE_LIMIT) return false;

  await db
    .prepare('INSERT INTO login_attempts (ip, attempted_at) VALUES (?, ?)')
    .bind(ip, nowIso())
    .run();
  return true;
}

/** Po udanym logowaniu kasujemy licznik prób z danego IP. */
export async function clearRateLimit(db: D1Database, ip: string): Promise<void> {
  await db.prepare('DELETE FROM login_attempts WHERE ip = ?').bind(ip).run();
}

export function clientIp(request: Request): string {
  return (
    request.headers.get('CF-Connecting-IP') ??
    request.headers.get('X-Forwarded-For')?.split(',')[0]?.trim() ??
    'unknown'
  );
}
