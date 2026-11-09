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
 * Masowe przypisanie zaznaczonego sprzętu jednej osobie - nowy pracownik
 * dostaje zwykle komplet (laptop, monitor, telefon), a klikanie po kolei przez
 * kartę każdego sprzętu to kilkanaście kroków.
 *
 * Obowiązuje ta sama zasada co na karcie sprzętu: przypisać można tylko sprzęt
 * dostępny. Wycofany albo w serwisie wymaga najpierw zmiany statusu, a
 * przypisany komuś innemu - zwrotu, żeby historia nie zgubiła poprzedniej osoby.
 */
export const POST: APIRoute = async ({ locals, redirect }) => {
  const { t, session, db } = locals;

  const assetIds = [
    ...new Set(
      fieldList(locals.form, 'asset_pks')
        .map(parseInteger)
        .filter((n): n is number => n !== null && n > 0),
    ),
  ];
  const userId = parseInteger(field(locals.form, 'assign_user_id'));

  if (assetIds.length === 0) {
    session.addMessage(t.msg_bulk_none_selected);
    return redirect('/assets/');
  }
  if (userId === null) {
    session.addMessage(t.assets_bulk_pick_user);
    return redirect('/assets/');
  }

  const placeholders = assetIds.map(() => '?').join(', ');
  const [userResult, availableResult] = await db.batch([
    db.prepare('SELECT id, first_name, last_name FROM users WHERE id = ?').bind(userId),
    db
      .prepare(
        `SELECT id FROM assets
          WHERE id IN (${placeholders}) AND status = ? AND assigned_to_id IS NULL`,
      )
      .bind(...assetIds, ASSET_STATUS.AVAILABLE),
  ]);

  const user = (userResult.results as Pick<UserRow, 'id' | 'first_name' | 'last_name'>[])[0];
  if (!user) return redirect('/assets/');

  const available = (availableResult.results as { id: number }[]).map((r) => r.id);
  if (available.length === 0) {
    session.addMessage(t.msg_bulk_none_available);
    return redirect('/assets/');
  }

  await db.batch([
    db
      .prepare(
        `UPDATE assets
            SET assigned_to_id = ?, assigned_date = ?, status = ?, updated_at = ?
          WHERE id IN (${available.map(() => '?').join(', ')})`,
      )
      .bind(user.id, todayIso(), ASSET_STATUS.ASSIGNED, nowIso(), ...available),
    ...available.map((assetId) =>
      addHistory(db, {
        asset_id: assetId,
        action: HISTORY_ACTION.ASSIGN,
        user_id: user.id,
      }),
    ),
  ]);

  session.addMessage(
    fmt(t.msg_assets_assigned, { count: available.length, name: fullName(user) }),
  );
  const skipped = assetIds.length - available.length;
  if (skipped > 0) session.addMessage(fmt(t.msg_bulk_skipped, { count: skipped }));

  return redirect('/assets/');
};
