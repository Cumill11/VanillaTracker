import type { APIRoute } from 'astro';
import {
  ASSET_STATUS,
  HISTORY_ACTION,
  addHistory,
  fullName,
  nowIso,
  todayIso,
  type UserRow,
} from '../../../lib/db';
import { field, fieldList, parseInteger } from '../../../lib/forms';
import { fmt } from '../../../lib/i18n';

/**
 * Masowe przypisanie zaznaczonego sprzętu jednej osobie — nowy pracownik
 * dostaje zwykle komplet (laptop, monitor, telefon), a klikanie po kolei przez
 * kartę każdego sprzętu to kilkanaście kroków.
 */
export const POST: APIRoute = async ({ locals, redirect }) => {
  const { t, session, db } = locals;

  const assetIds = fieldList(locals.form, 'asset_pks')
    .map(parseInteger)
    .filter((n): n is number => n !== null && n > 0);
  const userId = parseInteger(field(locals.form, 'assign_user_id'));

  if (assetIds.length === 0) {
    session.addMessage(t.msg_bulk_none_selected);
    return redirect('/assets/');
  }
  if (userId === null) {
    session.addMessage(t.assets_bulk_pick_user);
    return redirect('/assets/');
  }

  const user = await db
    .prepare('SELECT id, first_name, last_name FROM users WHERE id = ?')
    .bind(userId)
    .first<Pick<UserRow, 'id' | 'first_name' | 'last_name'>>();

  if (!user) return redirect('/assets/');

  const placeholders = assetIds.map(() => '?').join(', ');
  const statements = [
    db
      .prepare(
        `UPDATE assets
            SET assigned_to_id = ?, assigned_date = ?, status = ?, updated_at = ?
          WHERE id IN (${placeholders})`,
      )
      .bind(user.id, todayIso(), ASSET_STATUS.ASSIGNED, nowIso(), ...assetIds),
    ...assetIds.map((assetId) =>
      addHistory(db, {
        asset_id: assetId,
        action: HISTORY_ACTION.ASSIGN,
        user_id: user.id,
      }),
    ),
  ];

  await db.batch(statements);

  session.addMessage(
    fmt(t.msg_assets_assigned, { count: assetIds.length, name: fullName(user) }),
  );
  return redirect('/assets/');
};
