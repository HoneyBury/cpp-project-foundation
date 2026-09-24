#include "hello/request_parser.h"

#include <cstddef>
#include <cstdint>
#include <string_view>

namespace service = hello;

extern "C" int LLVMFuzzerTestOneInput(const std::uint8_t* data, std::size_t size) {
    static_cast<void>(
        service::parse_request(std::string_view(reinterpret_cast<const char*>(data), size)));
    return 0;
}
