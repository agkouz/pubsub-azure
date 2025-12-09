# ---- Build stage ----
FROM node:20-alpine AS builder
WORKDIR /app

# Install deps first (better layer caching)
COPY package.json package-lock.json* pnpm-lock.yaml* yarn.lock* ./
# Choose your installer (uncomment one)
# RUN corepack enable && corepack prepare pnpm@latest --activate && pnpm install --frozen-lockfile
RUN npm install
# should replace wit "ci"

# Copy the rest and build
COPY . .

# If you use env vars, set them as build args and map to Vite:
ARG VITE_BACKEND_URL=https://inrm-gateway-dgsi3cmf.ew.gateway.dev
# ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# ---- Runtime stage ----
FROM nginx:1.27-alpine AS runner
# Copy build output
COPY --from=builder /app/dist /usr/share/nginx/html

# Minimal Nginx config with SPA fallback + caching for hashed assets
RUN printf '%s\n' \
  'server {' \
  '  listen 8080;' \
  '  server_name _;' \
  '  root /usr/share/nginx/html;' \
  '' \
  '  # Serve static files and fall back to index.html for SPA routes' \
  '  location / {' \
  '    try_files $uri $uri/ /index.html;' \
  '  }' \
  '' \
  '  # Cache immutable assets produced by Vite (hashed filenames)' \
  '  location ~* ^/assets/.*\.(js|css|svg|png|jpg|jpeg|gif|webp|ico)$ {' \
  '    add_header Cache-Control "public, max-age=31536000, immutable";' \
  '    try_files $uri =404;' \
  '  }' \
  '' \
  '  # Basic security headers (tweak for your needs)' \
  '  add_header X-Content-Type-Options nosniff;' \
  '  add_header X-Frame-Options SAMEORIGIN;' \
  '  add_header Referrer-Policy no-referrer-when-downgrade;' \
  '}' \
  > /etc/nginx/conf.d/default.conf

EXPOSE 8080

# Optional healthcheck (requires curl in image)

#RUN apk add --no-cache curl
#HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -f http://localhost/ || exit 1

# Nginx is the default CMD
