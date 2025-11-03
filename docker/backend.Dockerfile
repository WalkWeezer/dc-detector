FROM node:20-bullseye-slim
WORKDIR /app

# Копируем только package.json, чтобы не тянуть старый lock с нативными зависимостями (например, canvas)
COPY services/backend/package.json ./
# Устанавливаем без dev и optional зависимостей (избегаем сборки нативных модулей на Pi)
RUN npm install --omit=dev --omit=optional --no-audit --no-fund && npm cache clean --force

COPY services/backend ./
COPY infra/db/migrations ./infra/db/migrations

ENV NODE_ENV=production
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --retries=3 CMD node -e "fetch('http://localhost:8080/health',{keepalive:true}).then(r=>{if(!r.ok)process.exit(1)}).catch(()=>process.exit(1))"
USER node
CMD ["node", "src/server.js"]


