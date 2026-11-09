-- Usuwa kolumnę `assets.name`.
--
-- Nazwa sprzętu była wyłącznie sklejeniem producenta i modelu - w formularzu
-- puste pole i tak wypełniało się automatycznie, a listy pokazywały tę samą
-- treść dwa razy (kolumna „Nazwa" i „Producent / Model"). Teraz nazwa powstaje
-- przy wyświetlaniu, z dwóch pól, które faktycznie wprowadza użytkownik.
--
-- Gdyby w istniejących danych nazwa niosła coś ponad producenta i model,
-- przenosimy ją do modelu, żeby nic nie przepadło.
UPDATE assets
   SET model_name = TRIM(name)
 WHERE TRIM(COALESCE(model_name, '')) = ''
   AND TRIM(COALESCE(name, '')) <> '';

ALTER TABLE assets DROP COLUMN name;
