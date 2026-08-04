/**
 * Middleware: nagłówki bezpieczeństwa, sesja, ochrona CSRF, odczyt formularza
 * i wymóg zalogowania.
 *
 * Zastępuje `@app.before_request`, `login_required` i `verify_csrf` z wersji
 * Flask. CSRF sprawdzamy centralnie dla każdego żądania zmieniającego stan,
 * więc pojedyncza trasa nie może o tym zapomnieć.
 */
import { defineMiddleware } from 'astro:middleware';
import { isPublicPath } from './lib/auth';
import { env } from './lib/env';
import { renderErrorPage } from './lib/errorPage';
import { translations } from './lib/i18n';
import { COOKIE_NAME, SESSION_COOKIE_OPTIONS, Session } from './lib/session';

const UNSAFE_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

/**
 * Nagłówki dokładane do każdej odpowiedzi workera.
 *
 * Plik `public/_headers` ustawia te same wartości, ale Cloudflare stosuje go
 * wyłącznie do zasobów statycznych — strony generowane przez workera trzeba
 * oznaczyć tutaj. Zmieniając jedno miejsce, popraw też drugie.
 */
const SECURITY_HEADERS: Record<string, string> = {
  // Zakaz osadzania w ramce — zamyka clickjacking.
  'X-Frame-Options': 'DENY',
  'X-Content-Type-Options': 'nosniff',
  'Referrer-Policy': 'strict-origin-when-cross-origin',
};

function secured(response: Response): Response {
  for (const [name, value] of Object.entries(SECURITY_HEADERS)) {
    response.headers.set(name, value);
  }
  return response;
}

export const onRequest = defineMiddleware(async (context, next) => {
  const { locals, request, url, cookies } = context;

  locals.t = translations;
  locals.form = new FormData();

  const secret = env.SESSION_SECRET;
  if (!secret || !env.DB) {
    return secured(
      new Response(
        'Brak konfiguracji: ustaw sekret SESSION_SECRET oraz binding D1 o nazwie DB.',
        { status: 500, headers: { 'content-type': 'text/plain; charset=utf-8' } },
      ),
    );
  }

  locals.db = env.DB;

  const session = await Session.load(cookies.get(COOKIE_NAME)?.value, secret);
  locals.session = session;
  locals.isAdmin = session.isAdmin;

  /**
   * Zapisuje sesję, jeśli zmieniła się w trakcie żądania. Astro dokleja
   * ciasteczka do odpowiedzi po zakończeniu całego łańcucha middleware,
   * więc zapis po `next()` też zadziała.
   */
  const persistSession = async (): Promise<void> => {
    if (!session.dirty) return;
    cookies.set(COOKIE_NAME, await session.serialize(secret), SESSION_COOKIE_OPTIONS);
  };

  const pathname = url.pathname;

  // Ochrona CSRF — token z sesji musi zgadzać się z polem formularza.
  if (UNSAFE_METHODS.has(request.method)) {
    const contentType = request.headers.get('content-type') ?? '';
    const isForm =
      contentType.includes('application/x-www-form-urlencoded') ||
      contentType.includes('multipart/form-data');

    if (!isForm) return secured(renderErrorPage(403));

    // Ciało czytamy raz i udostępniamy stronom przez `locals.form`. Wcześniej
    // middleware klonował żądanie tylko po token, a strona parsowała je drugi raz.
    try {
      locals.form = await request.formData();
    } catch {
      return secured(renderErrorPage(403));
    }

    const token = locals.form.get('csrf_token');
    if (!session.verifyCsrf(typeof token === 'string' ? token : null)) {
      return secured(renderErrorPage(403));
    }
  }

  // Wymóg zalogowania (odpowiednik `login_required` na każdej trasie).
  if (!session.isAdmin && !isPublicPath(pathname)) {
    const target = `${pathname}${url.search}`;
    await persistSession();
    return secured(context.redirect(`/login/?next=${encodeURIComponent(target)}`));
  }

  const response = await next();
  await persistSession();
  return secured(response);
});
