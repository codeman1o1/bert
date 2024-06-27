# Until Pocketbase hits stable, there will be no official Docker image.

FROM alpine:3

ARG TARGETOS
ARG TARGETARCH
ARG TARGETVARIANT
ARG VERSION
ARG PB_EMAIL
ARG PB_PASSWORD

ENV BUILDX_ARCH="${TARGETOS:-linux}_${TARGETARCH:-amd64}${TARGETVARIANT}"

ADD https://github.com/pocketbase/pocketbase/releases/download/v${VERSION}/pocketbase_${VERSION}_${BUILDX_ARCH}.zip /tmp/pb.zip
RUN apk --no-cache add unzip ca-certificates \
    && unzip /tmp/pb.zip \
    && mv pocketbase /usr/local/bin \
    && rm /tmp/pb.zip \
    && chmod +x /usr/local/bin/pocketbase

RUN /usr/local/bin/pocketbase --dir=/pb_data migrate up \
    && /usr/local/bin/pocketbase --dir=/pb_data admin create $PB_EMAIL $PB_PASSWORD

COPY index.html /pb_public/index.html

EXPOSE 8090

ENTRYPOINT ["/usr/local/bin/pocketbase", "serve", "--http=0.0.0.0:8090", "--dir=/pb_data", "--publicDir=/pb_public", "--migrationsDir=/pb_migrations", "--hooksDir=/pb_hooks"]
