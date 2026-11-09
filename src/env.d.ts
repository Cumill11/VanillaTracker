/// <reference types="astro/client" />

declare namespace App {
  interface Locals {
    /** Baza D1, wstawiana przez middleware. */
    db: import('@cloudflare/workers-types').D1Database;
    session: import('./lib/session').Session;
    t: import('./lib/i18n').Translations;
    /** Ciało formularza, sparsowane raz w middleware (puste dla GET). */
    form: FormData;
  }
}
