import type { APIRoute } from 'astro';

/** Wylogowanie — CSRF sprawdza middleware. */
export const POST: APIRoute = ({ locals, redirect }) => {
  locals.session.logout();
  return redirect('/login/');
};
