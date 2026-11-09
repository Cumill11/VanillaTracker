import type { APIRoute } from 'astro';
import {
  ASSET_STATUS,
  HISTORY_ACTION,
  addHistory,
  fullName,
  nowIso,
  type AssetRow,
  type UserRow,
} from '../../../../lib/db';
import { field, parseDate, parseId, parseInteger } from '../../../../lib/forms';
import { fmt } from '../../../../lib/i18n';

/** Przypisanie sprzętu do osoby - port `POST /assets/<pk>/assign/`. */
export const POST: APIRoute = async ({ params, locals, redirect }) => {
  const { t, session, db } = locals;

  const id = parseId(params.id);
  if (id === null) return redirect('/assets/');

  const form = locals.form;
  const userId = parseInteger(field(form, 'assign_user_id'));
  const assignedDate = parseDate(field(form, 'assigned_date'));
  const note = field(form, 'note');

  // Sprzęt i osoba są wyszukiwane niezależnie, więc jednym okrążeniem.
  const [assetResult, userResult] = await db.batch([
    db.prepare('SELECT id, asset_tag, status, assigned_to_id FROM assets WHERE id = ?').bind(id),
    db.prepare('SELECT id, first_name, last_name FROM users WHERE id = ?').bind(userId ?? 0),
  ]);

  const asset = (
    assetResult.results as Pick<AssetRow, 'id' | 'asset_tag' | 'status' | 'assigned_to_id'>[]
  )[0];

  // Przypisać można tylko sprzęt dostępny - karta sprzętu pokazuje formularz
  // wyłącznie wtedy, a tu pilnujemy tego samego po stronie serwera.
  const assignable =
    asset && asset.status === ASSET_STATUS.AVAILABLE && asset.assigned_to_id === null;

  if (assignable && userId !== null) {
    const user = (userResult.results as Pick<UserRow, 'id' | 'first_name' | 'last_name'>[])[0];

    if (user) {
      await db.batch([
        db
          .prepare(
            `UPDATE assets
                SET assigned_to_id = ?, assigned_date = ?, status = ?, updated_at = ?
              WHERE id = ?`,
          )
          .bind(user.id, assignedDate, ASSET_STATUS.ASSIGNED, nowIso(), id),
        addHistory(db, {
          asset_id: id,
          action: HISTORY_ACTION.ASSIGN,
          user_id: user.id,
          note,
        }),
      ]);
      session.addMessage(
        fmt(t.msg_asset_assigned, { tag: asset.asset_tag, name: fullName(user) }),
      );
    }
  }

  return redirect(`/assets/${id}/`);
};
