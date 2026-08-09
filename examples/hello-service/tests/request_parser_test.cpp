#include "hello/request_parser.h"

#include <cstdlib>

int main() {
    if (hello::parse_request("GET /health HTTP/1.1\r\n") !=
        hello::RequestKind::health) return EXIT_FAILURE;
    if (hello::parse_request("GET /metrics HTTP/1.1\r\n") !=
        hello::RequestKind::metrics) return EXIT_FAILURE;
    if (hello::parse_request("POST /health HTTP/1.1\r\n") !=
        hello::RequestKind::unknown) return EXIT_FAILURE;
    if (hello::parse_request("invalid") != hello::RequestKind::unknown)
        return EXIT_FAILURE;
    return EXIT_SUCCESS;
}
