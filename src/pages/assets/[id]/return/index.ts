import type { APIRoute } from 'astro';
import { ASSET_STATUS, HISTORY_ACTION, addHistory, nowIso, type AssetRow } from '../../../../lib/db';
import { field, parseId } from '../../../../lib/forms';
import { fmt } from '../../../../lib/i18n';

/** Zwrot sprzętu — port `POST /assets/<pk>/return/`. */
export const POST: APIRoute = async ({ params, locals, redirect }) => {
  const { t, session, db } = locals;

  const id = parseId(params.id);
  if (id === null) return redirect('/assets/');

  const note = field(locals.form, 'note');

  const asset = await db
    .prepare('SELECT id, asset_tag, assigned_to_id, department_id FROM assets WHERE id = ?')
    .bind(id)
    .first<Pick<AssetRow, 'id' | 'asset_tag' | 'assigned_to_id' | 'department_id'>>();

  if (asset) {
    // Sprzęt przypisany do działu pozostaje „przypisany" nawet po zwrocie od osoby.
    const newStatus = asset.department_id ? ASSET_STATUS.ASSIGNED : ASSET_STATUS.AVAILABLE;

    await db.batch([
      addHistory(db, {
        asset_id: id,
        action: HISTORY_ACTION.RETURN,
        user_id: asset.assigned_to_id,
        note,
      }),
      db
        .prepare(
          `UPDATE assets
              SET assigned_to_id = NULL, assigned_date = NULL, status = ?, updated_at = ?
            WHERE id = ?`,
        )
        .bind(newStatus, nowIso(), id),
    ]);

    session.addMessage(fmt(t.msg_asset_returned, { tag: asset.asset_tag }));
  }

  return redirect(`/assets/${id}/`);
};
