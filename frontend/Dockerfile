FROM node:26-alpine

WORKDIR /app

# Install the exact versions from package-lock.json first, so this layer is cached until it changes.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
