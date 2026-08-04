FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1

# Daemon mode: 30-minute scan loop + Telegram admin commands.
# For a one-shot run (e.g. cron), use: docker run ... python -m university_intel.worker --once
CMD ["python", "-m", "university_intel.worker"]
