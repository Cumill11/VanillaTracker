FROM python:3.14-slim

# Bez bytecode na dysku, niebuforowane logi
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# app.py oczekuje struktury <PROJECT_ROOT>/vanillatracker/app.py
WORKDIR /app/vanillatracker

# Zależności osobno — lepsze cache'owanie warstw
COPY vanillatracker/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Kod aplikacji
COPY vanillatracker/ ./

# Uruchomienie jako użytkownik nie-root
RUN useradd --create-home --uid 1000 appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

# Serwer produkcyjny WSGI (nie deweloperski app.run)
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "60", "app:app"]
