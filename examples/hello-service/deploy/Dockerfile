FROM ubuntu:24.04@sha256:534baea6a22c03a63003dbc8dbe78fe34bc0d7e595d9a9dc9834884ff530eb55
RUN useradd --system --uid 10001 --no-create-home app
COPY bin/hello-service /usr/local/bin/hello-service
USER 10001:10001
EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/hello-service"]
