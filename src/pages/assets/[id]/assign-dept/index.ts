import type { APIRoute } from 'astro';
import {
  ASSET_STATUS,
  HISTORY_ACTION,
  addHistory,
  nowIso,
  type AssetRow,
  type DepartmentRow,
} from '../../../../lib/db';
import { field, parseId, parseInteger } from '../../../../lib/forms';
import { fmt } from '../../../../lib/i18n';
import { NOTES } from '../../../../lib/notes';

/** Przypisanie sprzętu do działu - port `POST /assets/<pk>/assign-dept/`. */
export const POST: APIRoute = async ({ params, locals, redirect }) => {
  const { t, session, db } = locals;

  const id = parseId(params.id);
  if (id === null) return redirect('/assets/');

  const departmentId = parseInteger(field(locals.form, 'department_id'));

  const asset = await db
    .prepare('SELECT id, asset_tag, assigned_to_id, status FROM assets WHERE id = ?')
    .bind(id)
    .first<Pick<AssetRow, 'id' | 'asset_tag' | 'assigned_to_id' | 'status'>>();

  if (asset) {
    const department =
      departmentId === null
        ? null
        : await db
            .prepare('SELECT id, name FROM departments WHERE id = ?')
            .bind(departmentId)
            .first<DepartmentRow>();

    let note: string;
    let status = asset.status;

    if (department) {
      status = ASSET_STATUS.ASSIGNED;
      note = NOTES.dept(department.name);
      session.addMessage(
        fmt(t.msg_asset_dept_set, { tag: asset.asset_tag, name: department.name }),
      );
    } else {
      // Bez działu i bez osoby sprzęt wraca do puli dostępnych.
      if (!asset.assigned_to_id) status = ASSET_STATUS.AVAILABLE;
      note = NOTES.DEPT_CLEARED;
      session.addMessage(fmt(t.msg_asset_dept_cleared, { tag: asset.asset_tag }));
    }

    await db.batch([
      db
        .prepare('UPDATE assets SET department_id = ?, status = ?, updated_at = ? WHERE id = ?')
        .bind(department?.id ?? null, status, nowIso(), id),
      addHistory(db, { asset_id: id, action: HISTORY_ACTION.ASSIGN_DEPT, note }),
    ]);
  }

  return redirect(`/assets/${id}/`);
};
