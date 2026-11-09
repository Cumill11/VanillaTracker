-- Aplikacja nie ma już logowania, więc licznik prób logowania jest zbędny.
-- Indeks `idx_login_attempts` znika razem z tabelą.
DROP TABLE IF EXISTS login_attempts;
