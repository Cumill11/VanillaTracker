/**
 * Formularze sprzętu, licencji i osób.
 *
 * Lista pól każdej encji jest jednym źródłem prawdy: wynika z niej typ danych
 * formularza, pusty formularz, odczyt z `FormData` i wypełnienie z wiersza bazy.
 * Dopisanie pola sprowadza się do dodania nazwy do listy i (jeśli trafia do
 * bazy) jednej linii w `columns`.
 */
import { LICENSE_STATUS, effectiveLicenseStatus } from './db';
import {
  field,
  parseDate,
  parseDecimal,
  parseInteger,
  parseSeats,
  type Errors,
} from './forms';
import type { Translations } from './i18n';
import type { Columns } from './sql';

type FormOf<F extends readonly string[]> = Record<F[number], string>;

function buildForm<F extends readonly string[]>(
  fields: F,
  read: (key: F[number]) => unknown,
  defaults: Partial<FormOf<F>>,
): FormOf<F> {
  const out: Record<string, string> = {};
  for (const key of fields) {
    const raw = read(key as F[number]);
    const value = raw === null || raw === undefined ? '' : String(raw);
    out[key] = value || (defaults as Record<string, string>)[key] || '';
  }
  return out as FormOf<F>;
}

const emptyForm = <F extends readonly string[]>(fields: F, defaults: Partial<FormOf<F>> = {}) =>
  buildForm(fields, () => '', defaults);

const readForm = <F extends readonly string[]>(
  form: FormData,
  fields: F,
  defaults: Partial<FormOf<F>> = {},
) => buildForm(fields, (key) => field(form, key), defaults);

const formFromRow = <F extends readonly string[]>(
  row: object,
  fields: F,
  defaults: Partial<FormOf<F>> = {},
) => buildForm(fields, (key) => (row as Record<string, unknown>)[key], defaults);

const required = (t: Translations) => [t.lbl_required];

// ── Sprzęt ──────────────────────────────────────────────────────────────────

const ASSET_FIELDS = [
  'category_id',
  'manufacturer',
  'model_name',
  'serial_number',
  'purchase_date',
  'purchase_price',
  'warranty_expiry',
  'notes',
  'cpu',
  'ram',
  'storage',
  'phone_number',
  'ink_type',
] as const;

export type AssetFormData = FormOf<typeof ASSET_FIELDS>;

export const assetForm = {
  empty: () => emptyForm(ASSET_FIELDS),
  read: (form: FormData) => readForm(form, ASSET_FIELDS),
  fromRow: (row: object) => formFromRow(row, ASSET_FIELDS),

  /** Port `_validate_asset` - wymagane: kategoria, producent, model. */
  validate(data: AssetFormData, t: Translations): Errors {
    const errors: Errors = {};
    if (parseInteger(data.category_id) === null) errors.category = required(t);
    if (!data.manufacturer.trim()) errors.manufacturer = required(t);
    if (!data.model_name.trim()) errors.model_name = required(t);
    return errors;
  },

  columns(data: AssetFormData): Columns {
    return {
      category_id: parseInteger(data.category_id),
      manufacturer: data.manufacturer.trim(),
      model_name: data.model_name.trim(),
      serial_number: data.serial_number.trim() || null,
      purchase_date: parseDate(data.purchase_date),
      purchase_price: parseDecimal(data.purchase_price),
      warranty_expiry: parseDate(data.warranty_expiry),
      notes: data.notes.trim(),
      cpu: data.cpu.trim(),
      ram: data.ram.trim(),
      storage: data.storage.trim(),
      phone_number: data.phone_number.trim(),
      ink_type: data.ink_type.trim(),
    };
  },
};

// ── Licencje ────────────────────────────────────────────────────────────────

const LICENSE_FIELDS = [
  'name',
  'vendor',
  'license_key',
  'seats',
  'purchase_date',
  'expiry_date',
  'purchase_price',
  'status',
  'notes',
] as const;

const LICENSE_DEFAULTS = { seats: '1', status: LICENSE_STATUS.ACTIVE };

export type LicenseFormData = FormOf<typeof LICENSE_FIELDS>;

export const licenseForm = {
  empty: () => emptyForm(LICENSE_FIELDS, LICENSE_DEFAULTS),
  read: (form: FormData) => readForm(form, LICENSE_FIELDS, LICENSE_DEFAULTS),

  fromRow(row: object) {
    const data = formFromRow(row, LICENSE_FIELDS, LICENSE_DEFAULTS);
    // „expired" nie jest wyborem użytkownika - w formularzu pokazujemy „active".
    if (data.status !== LICENSE_STATUS.INACTIVE) data.status = LICENSE_STATUS.ACTIVE;
    return data;
  },

  validate(data: LicenseFormData, t: Translations): Errors {
    return data.name.trim() ? {} : { name: required(t) };
  },

  columns(data: LicenseFormData): Columns {
    const expiry = parseDate(data.expiry_date);
    return {
      name: data.name.trim(),
      vendor: data.vendor.trim(),
      license_key: data.license_key.trim(),
      seats: parseSeats(data.seats),
      purchase_date: parseDate(data.purchase_date),
      expiry_date: expiry,
      purchase_price: parseDecimal(data.purchase_price),
      status: effectiveLicenseStatus(expiry, data.status),
      notes: data.notes.trim(),
    };
  },
};

// ── Osoby ───────────────────────────────────────────────────────────────────

const USER_FIELDS = [
  'first_name',
  'last_name',
  'email',
  'department_id',
  'position',
  'phone',
] as const;

export type UserFormData = FormOf<typeof USER_FIELDS>;

export const userForm = {
  empty: () => emptyForm(USER_FIELDS),
  read: (form: FormData) => readForm(form, USER_FIELDS),
  fromRow: (row: object) => formFromRow(row, USER_FIELDS),

  validate(data: UserFormData, t: Translations): Errors {
    const errors: Errors = {};
    if (!data.first_name.trim()) errors.first_name = required(t);
    if (!data.last_name.trim()) errors.last_name = required(t);
    return errors;
  },

  columns(data: UserFormData): Columns {
    return {
      first_name: data.first_name.trim(),
      last_name: data.last_name.trim(),
      email: data.email.trim(),
      phone: data.phone.trim(),
      position: data.position.trim(),
      department_id: parseInteger(data.department_id),
    };
  },
};
