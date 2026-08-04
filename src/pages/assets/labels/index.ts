import type { APIRoute } from 'astro';
import { fieldList, parseInteger } from '../../../lib/forms';
import { generateLabelsPdf, pdfResponse } from '../../../lib/labels';

/** Etykiety zbiorcze — port `POST /assets/labels/`. */
export const POST: APIRoute = async ({ locals, url, redirect }) => {
  const { t, session, db } = locals;

  const form = locals.form;
  const ids = fieldList(form, 'asset_pks')
    .map(parseInteger)
    .filter((n): n is number => n !== null && n > 0);

  if (ids.length === 0) {
    session.addMessage(t.msg_labels_none_selected);
    return redirect('/assets/');
  }

  const placeholders = ids.map(() => '?').join(', ');
  const { results } = await db
    .prepare(
      `SELECT id, asset_tag FROM assets WHERE id IN (${placeholders}) ORDER BY tag_number`,
    )
    .bind(...ids)
    .all<{ id: number; asset_tag: string }>();

  if (!results || results.length === 0) {
    session.addMessage(t.msg_labels_not_found);
    return redirect('/assets/');
  }

  const pdf = await generateLabelsPdf(results, url.origin);
  return pdfResponse(pdf, 'etykiety.pdf');
};
