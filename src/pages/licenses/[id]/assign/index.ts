import type { APIRoute } from 'astro';
import type { D1PreparedStatement } from '@cloudflare/workers-types';
import { fieldList, parseId, parseInteger } from '../../../../lib/forms';

/** Przypisanie licencji do osób — port `POST /licenses/<pk>/assign/`. */
export const POST: APIRoute = async ({ params, locals, redirect }) => {
  const { t, session, db } = locals;

  const id = parseId(params.id);
  if (id === null) return redirect('/licenses/');

  const license = await db
    .prepare('SELECT id FROM licenses WHERE id = ?')
    .bind(id)
    .first<{ id: number }>();
  if (!license) return redirect('/licenses/');

  const userIds = fieldList(locals.form, 'users')
    .map(parseInteger)
    .filter((n): n is number => n !== null && n > 0);

  // Pełne zastąpienie listy — jak `lic.assigned_users = users` w SQLAlchemy.
  const statements: D1PreparedStatement[] = [
    db.prepare('DELETE FROM license_users WHERE license_id = ?').bind(id),
  ];

  if (userIds.length > 0) {
    const placeholders = userIds.map(() => '?').join(', ');
    statements.push(
      db
        .prepare(
          `INSERT INTO license_users (license_id, user_id)
             SELECT ?, id FROM users WHERE id IN (${placeholders})`,
        )
        .bind(id, ...userIds),
    );
  }

  await db.batch(statements);
  session.addMessage(t.msg_license_assignment_saved);
  return redirect(`/licenses/${id}/`);
};
