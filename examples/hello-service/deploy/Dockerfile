FROM ubuntu:24.10@sha256:cdf755952ed117f6126ff4e65810bf93767d4c38f5c7185b50ec1f1078b464cc
RUN useradd --system --uid 10001 --no-create-home app
COPY bin/hello-service /usr/local/bin/hello-service
USER 10001:10001
EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/hello-service"]
