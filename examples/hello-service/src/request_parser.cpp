#include "hello/request_parser.h"

namespace hello {

RequestKind parse_request(std::string_view request) noexcept {
    const auto first_space = request.find(' ');
    if (first_space == std::string_view::npos) return RequestKind::unknown;
    const auto second_space = request.find(' ', first_space + 1);
    if (second_space == std::string_view::npos) return RequestKind::unknown;
    const auto method = request.substr(0, first_space);
    const auto path = request.substr(first_space + 1, second_space - first_space - 1);
    if (method != "GET") return RequestKind::unknown;
    if (path == "/health") return RequestKind::health;
    if (path == "/metrics") return RequestKind::metrics;
    return RequestKind::unknown;
}

}  // namespace hello
