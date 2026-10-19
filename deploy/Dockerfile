FROM node:22-alpine AS frontend-build

WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS backend

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY backend/requirements-runtime.lock ./requirements-runtime.lock
RUN pip install --no-cache-dir -r requirements-runtime.lock \
    && groupadd --system app \
    && useradd --system --gid app --no-create-home --shell /usr/sbin/nologin app

COPY --chown=app:app backend/app ./backend/app

USER app
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/health/live', timeout=2)"
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-graceful-shutdown", "20", "--timeout-keep-alive", "5"]

FROM nginxinc/nginx-unprivileged:stable-alpine AS proxy

USER root
RUN mkdir -p /etc/nginx/certs
USER 101

COPY --from=frontend-build /frontend/dist/ /usr/share/nginx/html/
COPY deploy/reverse-proxy/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 8080 8443
