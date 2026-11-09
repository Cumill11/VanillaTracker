/**
 * Treści notatek zapisywanych w historii.
 *
 * To dane, a nie warstwa prezentacji - trafiają do bazy i mają zostać takie
 * same niezależnie od języka interfejsu, dlatego nie przechodzą przez i18n.
 */
export const NOTES = {
  ASSET_CREATED: 'Sprzęt dodany do systemu.',
  LICENSE_CREATED: 'Licencja dodana do systemu.',
  STATUS_AVAILABLE: 'Oznaczono jako dostępny.',
  STATUS_MAINTENANCE: 'Przekazano do serwisu.',
  STATUS_RETIRED: 'Wycofano z użytku.',
  DEPT_CLEARED: 'Usunięto przypisanie do działu',
  dept: (name: string) => `Dział: ${name}`,
} as const;

/** Notatki dla szybkiej zmiany statusu (port `_QUICK_STATUS_NOTES`). */
export const QUICK_STATUS_NOTES: Record<string, string> = {
  available: NOTES.STATUS_AVAILABLE,
  maintenance: NOTES.STATUS_MAINTENANCE,
  retired: NOTES.STATUS_RETIRED,
};

/** Statusy wymagające potwierdzenia (port `_STATUS_QUESTIONS`). */
export const STATUS_QUESTION_KEYS: Record<string, 'q_status_maintenance' | 'q_status_retired'> = {
  maintenance: 'q_status_maintenance',
  retired: 'q_status_retired',
};
