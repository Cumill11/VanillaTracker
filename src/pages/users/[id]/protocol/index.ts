import type { APIRoute } from 'astro';
import { ASSET_STATUS, assetName, fullName, type UserRow } from '../../../../lib/db';
import { formatDate } from '../../../../lib/format';
import { parseId } from '../../../../lib/forms';
import { pdfResponse } from '../../../../lib/labels';
import { generateProtocolPdf } from '../../../../lib/protocol';

type ProtocolUser = UserRow & { department_name: string | null };
type ProtocolAssetRow = {
  asset_tag: string;
  manufacturer: string;
  model_name: string;
  serial_number: string | null;
};

/** Protokół przekazania sprzętu dla osoby - `GET /users/<pk>/protocol/`. */
export const GET: APIRoute = async ({ params, locals, redirect }) => {
  const { t, db } = locals;

  const id = parseId(params.id);
  if (id === null) return redirect('/users/');

  const [userResult, assetsResult] = await db.batch([
    db
      .prepare(
        `SELECT u.*, d.name AS department_name
           FROM users u
           LEFT JOIN departments d ON d.id = u.department_id
          WHERE u.id = ?`,
      )
      .bind(id),
    db
      .prepare(
        `SELECT asset_tag, manufacturer, model_name, serial_number
           FROM assets
          WHERE assigned_to_id = ? AND status = ?
          ORDER BY tag_number`,
      )
      .bind(id, ASSET_STATUS.ASSIGNED),
  ]);

  const user = (userResult.results as ProtocolUser[])[0];
  if (!user) return redirect('/users/');

  const assets = (assetsResult.results as ProtocolAssetRow[]).map((asset) => ({
    asset_tag: asset.asset_tag,
    name: assetName(asset),
    serial_number: asset.serial_number,
  }));

  const pdf = await generateProtocolPdf(
    {
      name: fullName(user),
      position: user.position,
      department: user.department_name ?? '',
      email: user.email,
    },
    assets,
    t,
    formatDate(new Date().toISOString().slice(0, 10)),
  );

  return pdfResponse(pdf, `protokol-${user.last_name || user.id}.pdf`);
};
