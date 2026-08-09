#pragma once

#include <string_view>

namespace hello {

enum class RequestKind { health, metrics, unknown };

RequestKind parse_request(std::string_view request) noexcept;

}  // namespace hello
