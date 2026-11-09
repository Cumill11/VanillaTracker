/**
 * Sesja w podpisanym ciasteczku.
 *
 * Workers nie mają pamięci współdzielonej między requestami, więc cały stan
 * sesji (token CSRF, komunikaty flash) jedzie w ciasteczku
 * podpisanym HMAC-SHA256. Zawartość jest jawna, ale niemodyfikowalna bez
 * znajomości SESSION_SECRET.
 */
import { fromBase64Url, hmac, randomToken, timingSafeEqual, toBase64Url } from './crypto';

export const COOKIE_NAME = 'vt_session';
const MAX_AGE_SECONDS = 7 * 24 * 3600;

/** Opcje ciasteczka sesji (`Astro.cookies.set`). */
export const SESSION_COOKIE_OPTIONS = {
  path: '/',
  httpOnly: true,
  sameSite: 'strict',
  secure: true,
  maxAge: MAX_AGE_SECONDS,
} as const;

type SessionData = {
  /** Token CSRF. */
  c: string;
  /** Komunikaty flash. */
  m: string[];
  /** Wygaśnięcie (unix, sekundy). */
  e: number;
};

const encoder = new TextEncoder();
const decoder = new TextDecoder();

function nowSeconds(): number {
  return Math.floor(Date.now() / 1000);
}

function freshData(): SessionData {
  return { c: randomToken(), m: [], e: nowSeconds() + MAX_AGE_SECONDS };
}

export class Session {
  private data: SessionData;
  /** Ustawiane, gdy ciasteczko trzeba zapisać ponownie. */
  dirty = false;

  private constructor(data: SessionData, dirty: boolean) {
    this.data = data;
    this.dirty = dirty;
  }

  static async load(cookieValue: string | undefined, secret: string): Promise<Session> {
    const data = cookieValue ? await verifyCookie(cookieValue, secret) : null;
    if (!data) return new Session(freshData(), true);
    return new Session(data, false);
  }

  get csrfToken(): string {
    return this.data.c;
  }

  addMessage(text: string): void {
    this.data.m.push(text);
    this.dirty = true;
  }

  /** Zwraca komunikaty i od razu je czyści (semantyka flash). */
  takeMessages(): string[] {
    if (this.data.m.length === 0) return [];
    const msgs = this.data.m;
    this.data.m = [];
    this.dirty = true;
    return msgs;
  }

  verifyCsrf(token: string | null | undefined): boolean {
    if (!token || !this.data.c) return false;
    return timingSafeEqual(encoder.encode(token), encoder.encode(this.data.c));
  }

  async serialize(secret: string): Promise<string> {
    this.data.e = nowSeconds() + MAX_AGE_SECONDS;
    const payload = toBase64Url(encoder.encode(JSON.stringify(this.data)));
    const sig = toBase64Url(await hmac(secret, payload));
    return `${payload}.${sig}`;
  }
}

async function verifyCookie(value: string, secret: string): Promise<SessionData | null> {
  const dot = value.lastIndexOf('.');
  if (dot <= 0) return null;

  const payload = value.slice(0, dot);
  const sig = value.slice(dot + 1);

  let given: Uint8Array;
  try {
    given = fromBase64Url(sig);
  } catch {
    return null;
  }

  const expected = await hmac(secret, payload);
  if (!timingSafeEqual(given, expected)) return null;

  try {
    const data = JSON.parse(decoder.decode(fromBase64Url(payload))) as SessionData;
    if (typeof data?.c !== 'string' || typeof data?.e !== 'number') return null;
    if (data.e < nowSeconds()) return null;
    return { c: data.c, m: Array.isArray(data.m) ? data.m : [], e: data.e };
  } catch {
    return null;
  }
}
