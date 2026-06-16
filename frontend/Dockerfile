# HomomicsLab Frontend
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/templates/default.conf.template

EXPOSE 80

# Substitute env vars into nginx config at startup.
CMD ["/bin/sh", "-c", "envsubst '\$NGINX_SERVER_NAME \$NGINX_BACKEND_HOST \$NGINX_BACKEND_PORT \$NGINX_CLIENT_MAX_BODY_SIZE' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'"]
