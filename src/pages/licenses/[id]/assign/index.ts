import type { APIRoute } from 'astro';
import { HISTORY_ACTION, addHistory, nowIso } from '../../../../lib/db';
import { fieldList, parseId, parseInteger } from '../../../../lib/forms';

/**
 * Przypisanie licencji do osób - port `POST /licenses/<pk>/assign/`.
 *
 * Formularz wysyła pełną listę zaznaczonych osób. Zapisujemy tylko różnicę
 * względem bazy, żeby każda zmiana trafiła do historii jako osobne
 * przypisanie albo odpięcie.
 */
export const POST: APIRoute = async ({ params, locals, redirect }) => {
  const { t, session, db } = locals;

  const id = parseId(params.id);
  if (id === null) return redirect('/licenses/');

  const requested = [
    ...new Set(
      fieldList(locals.form, 'users')
        .map(parseInteger)
        .filter((n): n is number => n !== null && n > 0),
    ),
  ];
  // `IN (NULL)` nie pasuje do niczego - pusta lista bez osobnej gałęzi.
  const placeholders = requested.map(() => '?').join(', ') || 'NULL';

  const [licenseResult, currentResult, usersResult] = await db.batch([
    db.prepare('SELECT id FROM licenses WHERE id = ?').bind(id),
    db.prepare('SELECT user_id FROM license_users WHERE license_id = ?').bind(id),
    // Pomijamy identyfikatory osób, których nie ma (np. usuniętych w międzyczasie).
    db.prepare(`SELECT id FROM users WHERE id IN (${placeholders})`).bind(...requested),
  ]);

  if (licenseResult.results.length === 0) return redirect('/licenses/');

  const current = new Set((currentResult.results as { user_id: number }[]).map((r) => r.user_id));
  const wanted = new Set((usersResult.results as { id: number }[]).map((r) => r.id));
  const added = [...wanted].filter((userId) => !current.has(userId));
  const removed = [...current].filter((userId) => !wanted.has(userId));

  if (added.length > 0 || removed.length > 0) {
    await db.batch([
      ...removed.flatMap((userId) => [
        db
          .prepare('DELETE FROM license_users WHERE license_id = ? AND user_id = ?')
          .bind(id, userId),
        addHistory(db, { license_id: id, action: HISTORY_ACTION.UNASSIGN, user_id: userId }),
      ]),
      ...added.flatMap((userId) => [
        db
          .prepare('INSERT OR IGNORE INTO license_users (license_id, user_id) VALUES (?, ?)')
          .bind(id, userId),
        addHistory(db, { license_id: id, action: HISTORY_ACTION.ASSIGN, user_id: userId }),
      ]),
      db.prepare('UPDATE licenses SET updated_at = ? WHERE id = ?').bind(nowIso(), id),
    ]);
  }

  session.addMessage(t.msg_license_assignment_saved);
  return redirect(`/licenses/${id}/`);
};
