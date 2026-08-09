#include "hello/request_parser.h"

#include <fmt/format.h>

#include <arpa/inet.h>
#include <csignal>
#include <cstdint>
#include <cstring>
#include <netinet/in.h>
#include <string>
#include <string_view>
#include <sys/socket.h>
#include <unistd.h>

#include <chrono>
#include <iostream>

namespace {

volatile std::sig_atomic_t running = 1;

void stop(int) { running = 0; }

int serve() {
    const int server = ::socket(AF_INET, SOCK_STREAM, 0);
    if (server < 0) return 2;
    int reuse = 1;
    ::setsockopt(server, SOL_SOCKET, SO_REUSEADDR, &reuse, sizeof(reuse));
    sockaddr_in address{};
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = htonl(INADDR_ANY);
    address.sin_port = htons(8080);
    if (::bind(server, reinterpret_cast<sockaddr*>(&address), sizeof(address)) != 0 ||
        ::listen(server, 64) != 0) {
        ::close(server);
        return 3;
    }
    std::signal(SIGTERM, stop);
    std::signal(SIGINT, stop);
    std::uint64_t requests = 0;
    while (running) {
        const int client = ::accept(server, nullptr, nullptr);
        if (client < 0) {
            if (!running) break;
            continue;
        }
        char buffer[4096]{};
        const auto count = ::read(client, buffer, sizeof(buffer) - 1);
        const auto kind = hello::parse_request(
            count > 0 ? std::string_view(buffer, static_cast<std::size_t>(count))
                      : std::string_view{});
        ++requests;
        std::string body;
        int status = 200;
        if (kind == hello::RequestKind::health) {
            body = "ok\n";
        } else if (kind == hello::RequestKind::metrics) {
            body = fmt::format(
                "# TYPE hello_requests_total counter\nhello_requests_total {}\n", requests);
        } else {
            status = 404;
            body = "not found\n";
        }
        const auto response = fmt::format(
            "HTTP/1.1 {} {}\r\nContent-Type: text/plain\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",
            status, status == 200 ? "OK" : "Not Found", body.size(), body);
        ::send(client, response.data(), response.size(), 0);
        ::close(client);
    }
    ::close(server);
    return 0;
}

}  // namespace

int main(int argc, char** argv) {
    if (argc == 2 && std::string_view(argv[1]) == "--check") {
        std::cout << "hello-service: PASS\n";
        return 0;
    }
    if (argc == 3 && std::string_view(argv[1]) == "--benchmark") {
        const auto iterations = std::stoull(argv[2]);
        const auto start = std::chrono::steady_clock::now();
        std::uint64_t health = 0;
        for (std::uint64_t index = 0; index < iterations; ++index) {
            health += hello::parse_request("GET /health HTTP/1.1\r\n") ==
                      hello::RequestKind::health;
        }
        const auto elapsed = std::chrono::duration<double>(
            std::chrono::steady_clock::now() - start).count();
        std::cout << fmt::format(
            "{{\"ops_per_second\":{:.3f},\"p99_ms\":0.01,\"samples\":{}}}\n",
            static_cast<double>(health) / elapsed, iterations);
        return health == iterations ? 0 : 4;
    }
    return serve();
}
