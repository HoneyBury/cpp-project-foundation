FROM ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3
RUN useradd --system --uid 10001 --no-create-home app
COPY bin/hello-service /usr/local/bin/hello-service
USER 10001:10001
EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/hello-service"]
