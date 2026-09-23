/**
 * Samodzielna strona błędu (403/404/429/500).
 *
 * Nie korzysta z layoutu ani z bazy, bo bywa zwracana z middleware — zanim
 * cokolwiek zdąży się wyrenderować. Odpowiada `error.html` z wersji Flask.
 */
import { translations as t, tk } from './i18n';

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

export function renderErrorPage(status: number): Response {
  const title = tk(t, `error_${status}_title`, t.error_title);
  const message = tk(t, `error_${status}_msg`, t.error_unknown);

  const html = `<!DOCTYPE html>
<html lang="pl" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>${status} — ${escapeHtml(title)}</title>
<link rel="icon" type="image/svg+xml" href="/img/logo.svg">
<link href="/fonts/fonts.css" rel="stylesheet">
<style>
  :root {
    --md-primary:#D0BCFF; --md-on-primary:#381E72;
    --md-background:#141218; --md-on-background:#E6E0E9;
    --md-surface-container:#211F26; --md-on-surface:#E6E0E9;
    --md-on-surface-variant:#CAC4D0; --md-outline-variant:#49454F;
    --md-error:#F2B8B5;
    font-family:'Lato',sans-serif;
  }
  *,*::before,*::after { box-sizing:border-box; margin:0; padding:0; }
  body { background:var(--md-background); color:var(--md-on-background);
         min-height:100vh; display:flex; align-items:center; justify-content:center; padding:24px; }
  .card { background:var(--md-surface-container); border:1px solid var(--md-outline-variant);
          border-radius:16px; padding:32px; max-width:460px; width:100%; }
  .code { font-size:56px; font-weight:300; color:var(--md-error); line-height:1; margin-bottom:8px; }
  h1 { font-size:20px; font-weight:400; color:var(--md-on-surface); margin-bottom:12px; }
  p { font-size:14px; color:var(--md-on-surface-variant); margin-bottom:28px; line-height:1.5; }
  a.btn { display:inline-block; padding:12px 24px; border-radius:50px; background:var(--md-primary);
          color:var(--md-on-primary); font-size:14px; font-weight:500; text-decoration:none; }
  a.btn:hover { opacity:.9; }
</style>
</head>
<body>
<div class="card">
  <div class="code">${status}</div>
  <h1>${escapeHtml(title)}</h1>
  <p>${escapeHtml(message)}</p>
  <a class="btn" href="/">${escapeHtml(t.error_btn_home)}</a>
</div>
</body>
</html>`;

  return new Response(html, {
    status,
    headers: { 'content-type': 'text/html; charset=utf-8' },
  });
}
