/**
 * Przenosi dane ze zrzutu MariaDB/MySQL starej aplikacji do schematu D1.
 *
 *   node scripts/import-mysql-dump.mjs <zrzut.sql> > import.sql
 *   npx wrangler d1 execute vanillatracker --local --file import.sql
 *
 * Schemat nowej aplikacji różni się od starego, więc dane trzeba zmapować:
 *   users + user_profiles → users        (bez loginu, hasła i uprawnień)
 *   assets                → bez `name` i `location`
 *   categories            → bez `description`
 *   asset_history         → bez `performed_by_id`
 *   settings, login_attempts → pomijane
 *
 * Znaczniki czasu zapisujemy w ISO-8601 z „Z": stara aplikacja trzymała czas
 * uniwersalny, a nowa formatuje go do strefy Europe/Warsaw przy wyświetlaniu.
 */
import { readFileSync } from 'node:fs';

const file = process.argv[2];
if (!file) {
  console.error('Użycie: node scripts/import-mysql-dump.mjs <zrzut.sql>');
  process.exit(1);
}

const dump = readFileSync(file, 'utf8');

/** Zamienia sekwencje escapowane przez MySQL na zwykłe znaki. */
function unescape(value) {
  const map = { n: '\n', r: '\r', t: '\t', 0: '\0', '\\': '\\', "'": "'", '"': '"', Z: '\x1a' };
  let out = '';
  for (let i = 0; i < value.length; i++) {
    if (value[i] === '\\' && i + 1 < value.length) {
      const next = value[++i];
      out += map[next] ?? next;
    } else {
      out += value[i];
    }
  }
  return out;
}

/** Rozbija listę `(...),(...)` na wiersze, pilnując apostrofów. */
function splitRows(block) {
  const rows = [];
  let row = [];
  let value = '';
  let inString = false;
  let inRow = false;

  for (let i = 0; i < block.length; i++) {
    const ch = block[i];
    if (inString) {
      if (ch === '\\') value += ch + (block[++i] ?? '');
      else if (ch === "'") { inString = false; value += ch; }
      else value += ch;
      continue;
    }
    if (ch === "'") { inString = true; value += ch; }
    else if (ch === '(' && !inRow) { inRow = true; row = []; value = ''; }
    else if (ch === ',' && inRow) { row.push(value.trim()); value = ''; }
    else if (ch === ')' && inRow) { row.push(value.trim()); rows.push(row); inRow = false; value = ''; }
    else if (inRow) value += ch;
  }
  return rows;
}

/** Wszystkie wiersze danej tabeli ze zrzutu, jako obiekty kolumna → wartość. */
function readTable(table) {
  const pattern = new RegExp(
    'INSERT INTO `' + table + '` \\(([^)]*)\\) VALUES\\s*([\\s\\S]*?);\\s*\\n',
    'g',
  );
  const rows = [];
  for (const match of dump.matchAll(pattern)) {
    const columns = match[1].split(',').map((c) => c.trim().replace(/`/g, ''));
    for (const raw of splitRows(match[2])) {
      const row = {};
      columns.forEach((column, i) => {
        const value = raw[i];
        row[column] = value === 'NULL' ? null : value.startsWith("'") ? unescape(value.slice(1, -1)) : value;
      });
      rows.push(row);
    }
  }
  return rows;
}

const sqlText = (value) =>
  value === null || value === undefined ? 'NULL' : `'${String(value).replace(/'/g, "''")}'`;
const sqlNumber = (value) =>
  value === null || value === undefined || value === '' ? 'NULL' : String(Number(value));
/** `0000-00-00` z MySQL-a to brak daty. */
const sqlDate = (value) => (!value || value.startsWith('0000') ? 'NULL' : sqlText(value));
const sqlDateTime = (value) =>
  !value || value.startsWith('0000') ? 'NULL' : sqlText(value.replace(' ', 'T') + '.000Z');
const text = (value) => sqlText(value ?? '');

const users = readTable('users');
const profiles = new Map(readTable('user_profiles').map((p) => [p.user_id, p]));
const assets = readTable('assets');
const categories = readTable('categories');
const departments = readTable('departments');
const licenses = readTable('licenses');
const licenseUsers = readTable('license_users');
const history = readTable('asset_history');
const counter = readTable('asset_counter');
const tagPool = readTable('tag_pool');

const lines = [];
const emit = (line) => lines.push(line);

emit('-- Dane przeniesione ze zrzutu ' + file);
emit('-- Wygenerowane przez scripts/import-mysql-dump.mjs');
emit('');
emit('-- Czyścimy tabele w kolejności odwrotnej do zależności.');
for (const table of ['asset_history', 'license_users', 'licenses', 'assets', 'users',
                     'departments', 'categories', 'tag_pool', 'asset_counter']) {
  emit(`DELETE FROM ${table};`);
}
emit('');

/** Wstawia wiersze paczkami, żeby nie generować tysiąca osobnych zapytań. */
function insert(table, columns, rows, toValues, chunk = 50) {
  if (rows.length === 0) return;
  emit(`-- ${table}: ${rows.length}`);
  for (let i = 0; i < rows.length; i += chunk) {
    const values = rows.slice(i, i + chunk).map((row) => `  (${toValues(row).join(', ')})`);
    emit(`INSERT INTO ${table} (${columns.join(', ')}) VALUES`);
    emit(values.join(',\n') + ';');
  }
  emit('');
}

insert('categories', ['id', 'name', 'slug'], categories, (c) => [
  sqlNumber(c.id), text(c.name), text(c.slug),
]);

insert('departments', ['id', 'name'], departments, (d) => [sqlNumber(d.id), text(d.name)]);

insert(
  'users',
  ['id', 'first_name', 'last_name', 'email', 'phone', 'position', 'department_id', 'created_at'],
  users,
  (u) => {
    const profile = profiles.get(u.id) ?? {};
    return [
      sqlNumber(u.id), text(u.first_name), text(u.last_name), text(u.email),
      text(profile.phone), text(profile.position), sqlNumber(profile.department_id),
      sqlDateTime(u.date_joined) === 'NULL' ? sqlText(new Date().toISOString()) : sqlDateTime(u.date_joined),
    ];
  },
);

insert(
  'assets',
  ['id', 'asset_tag', 'tag_number', 'category_id', 'manufacturer', 'model_name', 'serial_number',
   'purchase_date', 'purchase_price', 'warranty_expiry', 'status', 'assigned_to_id',
   'assigned_date', 'department_id', 'notes', 'cpu', 'ram', 'storage', 'phone_number',
   'ink_type', 'created_at', 'updated_at'],
  assets,
  (a) => [
    sqlNumber(a.id), text(a.asset_tag), sqlNumber(a.tag_number), sqlNumber(a.category_id),
    text(a.manufacturer), text(a.model_name),
    a.serial_number ? sqlText(a.serial_number) : 'NULL',
    sqlDate(a.purchase_date),
    a.purchase_price === null || a.purchase_price === '' ? 'NULL' : sqlText(a.purchase_price),
    sqlDate(a.warranty_expiry), text(a.status), sqlNumber(a.assigned_to_id),
    sqlDate(a.assigned_date), sqlNumber(a.department_id), text(a.notes), text(a.cpu),
    text(a.ram), text(a.storage), text(a.phone_number), text(a.ink_type),
    sqlDateTime(a.created_at), sqlDateTime(a.updated_at),
  ],
);

insert(
  'licenses',
  ['id', 'asset_tag', 'tag_number', 'name', 'vendor', 'license_key', 'seats', 'purchase_date',
   'expiry_date', 'purchase_price', 'status', 'notes', 'created_at', 'updated_at'],
  licenses,
  (l) => [
    sqlNumber(l.id), text(l.asset_tag), sqlNumber(l.tag_number), text(l.name), text(l.vendor),
    text(l.license_key), sqlNumber(l.seats) === 'NULL' ? '1' : sqlNumber(l.seats),
    sqlDate(l.purchase_date), sqlDate(l.expiry_date),
    l.purchase_price === null || l.purchase_price === '' ? 'NULL' : sqlText(l.purchase_price),
    text(l.status), text(l.notes), sqlDateTime(l.created_at), sqlDateTime(l.updated_at),
  ],
);

insert('license_users', ['license_id', 'user_id'], licenseUsers, (lu) => [
  sqlNumber(lu.license_id), sqlNumber(lu.user_id),
]);

// Nowy schemat wymaga daty wpisu. W zrzucie trafiają się puste — bierzemy wtedy
// czas poprzedniego wpisu (rosnące id = rosnący czas), żeby wpis nie wylądował
// na szczycie osi czasu z datą importu.
let previousMoment = null;
for (const entry of history) {
  if (entry.created_at) previousMoment = entry.created_at;
  else entry.created_at = previousMoment;
}
const fallbackMoment = new Date().toISOString().replace('T', ' ').slice(0, 19);

insert(
  'asset_history',
  ['id', 'asset_id', 'license_id', 'action', 'user_id', 'note', 'created_at'],
  history,
  (h) => [
    sqlNumber(h.id), sqlNumber(h.asset_id), sqlNumber(h.license_id), text(h.action),
    sqlNumber(h.user_id), text(h.note), sqlDateTime(h.created_at ?? fallbackMoment),
  ],
);

insert('tag_pool', ['id', 'tag_number'], tagPool, (t) => [sqlNumber(t.id), sqlNumber(t.tag_number)]);

const lastNumber = counter[0]?.last_number ?? 0;
emit('-- Licznik numerów inwentarzowych');
emit(`INSERT INTO asset_counter (id, last_number) VALUES (1, ${Number(lastNumber)});`);

console.log(lines.join('\n'));

const skipped = assets.filter((a) => (a.name ?? '').trim()).length;
console.error(
  `Przeniesione: ${categories.length} kategorii, ${departments.length} działów, ` +
    `${users.length} osób, ${assets.length} sprzętu, ${licenses.length} licencji, ` +
    `${licenseUsers.length} przypisań licencji, ${history.length} wpisów historii. ` +
    `Licznik tagów: ${lastNumber}.`,
);
console.error(`Pominięte nazwy sprzętu (kolumna `.trim() + '`name` nie istnieje w nowym schemacie): ' + skipped);
