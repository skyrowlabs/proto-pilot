# Deliberately boring. Every generated app uses this exact file, so it is
# debugged once rather than once per prototype.
FROM python:3.12-slim

# Same vocabulary as compose.yml. Without this every prototype leaves an
# untraceable image behind -- the largest thing `gc` collects, and the one
# nothing else can attribute to a tree.
LABEL com.protopilot.slug="@@APP_SLUG@@" \
      com.protopilot.path="@@PROJECT_PATH@@" \
      com.protopilot.project="@@PROJECT@@"

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /srv

# Deps first so an app-code change does not invalidate the layer. The repair
# loop rebuilds often; this is the difference between 4s and 90s per attempt.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
