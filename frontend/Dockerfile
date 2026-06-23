# HomomicsLab Frontend
FROM node:20-alpine AS builder

WORKDIR /app

# Allow the API base URL to be overridden at build time.
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine

COPY --from=builder --chown=nginx:nginx /app/dist /usr/share/nginx/html
COPY --chown=nginx:nginx nginx.conf /etc/nginx/templates/default.conf.template

# Ensure nginx can write its cache, logs, pid file, and generated config.
RUN chown -R nginx:nginx /var/cache/nginx /var/log/nginx /etc/nginx/conf.d /etc/nginx/templates && \
    touch /var/run/nginx.pid && chown nginx:nginx /var/run/nginx.pid

# Run as an unprivileged user.
USER nginx

EXPOSE 8080

# Substitute env vars into nginx config at startup.
CMD ["/bin/sh", "-c", "envsubst '$NGINX_LISTEN_PORT $NGINX_SERVER_NAME $NGINX_BACKEND_HOST $NGINX_BACKEND_PORT $NGINX_CLIENT_MAX_BODY_SIZE' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'"]
