# Контекст сборки — корень репозитория (см. docker-compose.prod.yml): образу
# нужна и конфигурация nginx, и исходники React-админки.

# --- React-админка (admin-ui) → статика /panel/ ---
FROM node:22-alpine AS admin-ui
WORKDIR /build
RUN corepack enable
COPY admin-ui/package.json admin-ui/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY admin-ui/ ./
RUN pnpm build

# --- nginx ---
FROM nginx:1.26.0

COPY nginx/nginx.conf /etc/nginx/templates/default.conf.template
COPY nginx/nginx_entrypoint.sh /docker-entrypoint.d/.
COPY nginx/autorenew_hook.sh /etc/letsencrypt/renewal-hooks/deploy/.
RUN chmod +x /docker-entrypoint.d/nginx_entrypoint.sh
RUN apt update
RUN apt install certbot python3-certbot-nginx -y

COPY --from=admin-ui /build/dist /usr/share/nginx/panel
