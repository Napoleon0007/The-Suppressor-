# The Suppressor — container build.
# A Dockerfile (not nixpacks) so ffmpeg is guaranteed present at runtime —
# the video & audio chains shell out to it.
FROM python:3.12-slim

# ffmpeg for the media chains; clean up apt lists to keep the image small.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Railway provides $PORT; default to 8080 for local `docker run`.
CMD ["sh", "-c", "waitress-serve --host=0.0.0.0 --port=${PORT:-8080} app:app"]
