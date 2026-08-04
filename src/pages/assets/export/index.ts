import type { APIRoute } from 'astro';
import { ASSET_FROM, assetFilters } from '../../../lib/assetQuery';
import { assetName, fullName, type AssetRow } from '../../../lib/db';
import { tk } from '../../../lib/i18n';

type ExportRow = AssetRow & {
  category_name: string | null;
  category_slug: string | null;
  assigned_first_name: string | null;
  assigned_last_name: string | null;
  department_name: string | null;
};

/** W arkuszu pusta komórka czyta się lepiej niż półpauza z widoku HTML. */
const date = (value: string | null | undefined) => {
  if (!value) return '';
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  return m ? `${m[3]}.${m[2]}.${m[1]}` : value;
};

/** Pole CSV: cudzysłowy podwajamy, całość cytujemy — Excel nie lubi niespodzianek. */
const cell = (value: string | number | null | undefined) =>
  `"${String(value ?? '').replace(/"/g, '""')}"`;

/**
 * Eksport listy sprzętu do CSV — z tymi samymi filtrami, co widok listy.
 *
 * Separatorem jest średnik, a plik zaczyna się znacznikiem BOM: tak polski
 * Excel otwiera plik od razu w kolumnach i z poprawnymi ogonkami.
 */
export const GET: APIRoute = async ({ locals, url }) => {
  const { t, db } = locals;
  const { orderBy, where, args } = assetFilters(url.searchParams);

  const { results } = await db
    .prepare(
      `SELECT a.*, c.name AS category_name, c.slug AS category_slug,
              u.first_name AS assigned_first_name, u.last_name AS assigned_last_name,
              d.name AS department_name
         FROM ${ASSET_FROM}
         ${where}
        ORDER BY ${orderBy}`,
    )
    .bind(...args)
    .all<ExportRow>();

  const header = [
    t.assets_col_tag,
    t.lbl_name,
    t.asset_mfr,
    t.asset_model,
    t.assets_col_category,
    t.lbl_status,
    t.assets_col_assigned,
    t.user_dept,
    t.asset_serial,
    t.asset_purchase_date,
    t.asset_purchase_price,
    t.asset_warranty,
    t.asset_cpu,
    t.asset_ram,
    t.asset_storage,
    t.lbl_notes,
  ];

  const lines = [header.map(cell).join(';')];

  for (const asset of results ?? []) {
    const person = asset.assigned_to_id
      ? fullName({
          first_name: asset.assigned_first_name ?? '',
          last_name: asset.assigned_last_name ?? '',
        })
      : '';
    lines.push(
      [
        asset.asset_tag,
        assetName(asset),
        asset.manufacturer,
        asset.model_name,
        asset.category_slug ? tk(t, `cat_${asset.category_slug}`, asset.category_name ?? '') : '',
        tk(t, `status_${asset.status}`, asset.status),
        person,
        asset.department_name ?? '',
        asset.serial_number ?? '',
        date(asset.purchase_date),
        asset.purchase_price ?? '',
        date(asset.warranty_expiry),
        asset.cpu,
        asset.ram,
        asset.storage,
        asset.notes,
      ]
        .map(cell)
        .join(';'),
    );
  }

  const filename = `sprzet-${new Date().toISOString().slice(0, 10)}.csv`;

  return new Response('﻿' + lines.join('\r\n'), {
    headers: {
      'content-type': 'text/csv; charset=utf-8',
      'content-disposition': `attachment; filename="${filename}"`,
      'cache-control': 'no-store',
    },
  });
};
