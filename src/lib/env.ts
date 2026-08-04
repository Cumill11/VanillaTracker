/**
 * Dostęp do bindings i sekretów Workera.
 *
 * Od Astro 6 `Astro.locals.runtime.env` już nie istnieje — środowisko czyta się
 * z modułu `cloudflare:workers`. Trzymamy tu jedno, otypowane wejście, żeby
 * reszta kodu nie musiała rzutować.
 */
import { env as workerEnv } from 'cloudflare:workers';
import type { D1Database } from '@cloudflare/workers-types';

type AppEnv = {
  /** Baza D1 (binding `DB`). */
  DB: D1Database;
  /** Login administratora — sekret. */
  ADMIN_USERNAME?: string;
  /** Hasło administratora — sekret. */
  ADMIN_PASSWORD?: string;
  /** Klucz podpisujący ciasteczko sesji — sekret. */
  SESSION_SECRET?: string;
  /** Prefiks numerów inwentarzowych (zmienna, nie sekret). */
  TAG_PREFIX?: string;
};

export const env = workerEnv as unknown as AppEnv;
