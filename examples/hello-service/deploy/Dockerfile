FROM ubuntu:24.04@sha256:224a1869083a311ef3f13648a154ba79832fbef6364d31493642ca03082da254
RUN useradd --system --uid 10001 --no-create-home app
COPY bin/hello-service /usr/local/bin/hello-service
USER 10001:10001
EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/hello-service"]
