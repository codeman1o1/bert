FROM node:18-alpine

WORKDIR /usr/src/app

COPY package*.json ./

RUN npm ci --omit=dev

COPY . .

EXPOSE 3000

RUN npm run build

CMD [ "node", ".output/server/index.mjs" ]
