#include "hello/request_parser.h"

#include <cstdlib>

namespace service = hello;

int main() {
    if (service::parse_request("GET /health HTTP/1.1\r\n") != service::RequestKind::health)
        return EXIT_FAILURE;
    if (service::parse_request("GET /metrics HTTP/1.1\r\n") != service::RequestKind::metrics)
        return EXIT_FAILURE;
    if (service::parse_request("POST /health HTTP/1.1\r\n") != service::RequestKind::unknown)
        return EXIT_FAILURE;
    if (service::parse_request("GET /unknown HTTP/1.1\r\n") != service::RequestKind::unknown)
        return EXIT_FAILURE;
    if (service::parse_request("GET ") != service::RequestKind::unknown)
        return EXIT_FAILURE;
    if (service::parse_request("invalid") != service::RequestKind::unknown)
        return EXIT_FAILURE;
    return EXIT_SUCCESS;
}
