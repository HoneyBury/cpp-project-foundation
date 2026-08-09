FROM ubuntu:26.04@sha256:678c6550cc43645e08669028bc177f50be4e7c5b8cca677067b1914d4afc7a03
RUN useradd --system --uid 10001 --no-create-home app
COPY bin/hello-service /usr/local/bin/hello-service
USER 10001:10001
EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/hello-service"]
