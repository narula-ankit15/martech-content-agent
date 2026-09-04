# ---- frontend build ----
FROM node:20-alpine AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# Empty (not unset) VITE_API_BASE -- see frontend/src/api.js -- makes the
# built app call the API on its own origin, since one server serves both
# the static build and the API in production.
ENV VITE_API_BASE=""
RUN npm run build

# ---- backend runtime ----
FROM python:3.11-slim AS runtime
WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
# Seed data copied out of the mounted-volume path -- see
# docker-entrypoint.sh, which populates /app/data from here only if the
# volume is still empty, so it never clobbers real production content.
COPY data/projects/ ./seed-data/projects/
COPY data/assets/ ./seed-data/assets/
COPY --from=frontend-build /frontend/dist ./frontend_dist
COPY docker-entrypoint.sh ./

EXPOSE 8080
ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
