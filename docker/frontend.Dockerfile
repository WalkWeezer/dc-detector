FROM node:20-alpine AS build
WORKDIR /app

# Установка зависимостей: с lock — npm ci, без lock — npm install
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci || npm install

# Исходники фронтенда
COPY frontend ./

# Пытаемся собрать Vite/сборку; если dist не появился, формируем минимальный dist из статических файлов
RUN (npm run build 2>/dev/null || true) \
  && if [ ! -d dist ]; then \
       mkdir -p dist; \
       [ -f index.html ] && cp -f index.html dist/index.html || true; \
       [ -f app.js ] && cp -f app.js dist/app.js || true; \
       [ -f styles.css ] && cp -f styles.css dist/styles.css || true; \
     fi

FROM nginx:alpine
COPY --from=build /app/dist/ /usr/share/nginx/html/
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s --retries=3 CMD wget -qO- http://localhost/ >/dev/null || exit 1


