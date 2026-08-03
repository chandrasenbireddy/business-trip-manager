FROM python:3.11-slim

# browser-use (this version) drives a real Chromium over CDP, not
# Playwright/Selenium (see tools/model_router.py's scraper wiring) — needs an
# actual browser binary on the image. postgresql-client gives
# docker-entrypoint.sh pg_isready/psql to wait for and migrate the database.
RUN apt-get update && apt-get install -y --no-install-recommends \
        chromium \
        chromium-driver \
        postgresql-client \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    CHROMIUM_EXECUTABLE=/usr/bin/chromium

WORKDIR /app

COPY . .

# Editable install, not a real wheel build: tools/model_router.py resolves
# models.yaml via Path(__file__).parent.parent — a normal `pip install .`
# copies the package into site-packages, which breaks that path. `-e` keeps
# __file__ pointing at /app, same as local dev (README's `pip install
# -e ".[dev]"`), so the same path resolution works in both places.
RUN pip install --no-cache-dir -e .

RUN chmod +x docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]
