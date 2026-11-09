-- Usuwa kolumny, których aplikacja nigdy nie zapisuje ani nie pokazuje.
--
-- `assets.location`      - pozostałość po wersji Flask; formularz nie miał tego
--                          pola, więc wszędzie było pustym napisem.
-- `categories.description` - wybierana w każdym zapytaniu o kategorie, ale nigdy
--                          nierenderowana; niepotrzebnie czytana z bazy.
ALTER TABLE assets DROP COLUMN location;
ALTER TABLE categories DROP COLUMN description;
