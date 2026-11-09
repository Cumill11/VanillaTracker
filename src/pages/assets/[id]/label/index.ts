import type { APIRoute } from 'astro';
import { generateLabelsPdf, pdfResponse } from '../../../../lib/labels';
import { parseId } from '../../../../lib/forms';

/** Etykieta PDF pojedynczego sprzętu - port `GET /assets/<pk>/label/`. */
export const GET: APIRoute = async ({ params, locals, url, redirect }) => {
  const db = locals.db;

  const id = parseId(params.id);
  if (id === null) return redirect('/assets/');

  const asset = await db
    .prepare('SELECT id, asset_tag FROM assets WHERE id = ?')
    .bind(id)
    .first<{ id: number; asset_tag: string }>();

  if (!asset) return redirect('/assets/');

  const pdf = await generateLabelsPdf([asset], url.origin);
  return pdfResponse(pdf, `${asset.asset_tag}.pdf`);
};
