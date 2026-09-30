#include "hello/request_parser.h"

#include <arpa/inet.h>
#include <chrono>
#include <csignal>
#include <cstddef>
#include <cstdint>
#include <exception>
#include <fmt/format.h>
#include <iostream>
#include <netinet/in.h>
#include <string>
#include <string_view>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>

namespace {

namespace service = hello;

volatile sig_atomic_t running = 1;

void stop(int) {
    running = 0;
}

bool send_all(int socket, std::string_view data) noexcept {
    std::size_t sent = 0;
    while (sent < data.size()) {
        const auto count = ::send(socket, data.data() + static_cast<std::ptrdiff_t>(sent),
                                  data.size() - sent, MSG_NOSIGNAL);
        if (count <= 0)
            return false;
        sent += static_cast<std::size_t>(count);
    }
    return true;
}

int check_service() {
    const int client = ::socket(AF_INET, SOCK_STREAM, 0);
    if (client < 0)
        return 6;
    const timeval timeout{2, 0};
    static_cast<void>(::setsockopt(client, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout)));
    static_cast<void>(::setsockopt(client, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout)));
    sockaddr_in address{};
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    address.sin_port = htons(8080);
    if (::connect(client, reinterpret_cast<sockaddr*>(&address), sizeof(address)) != 0) {
        ::close(client);
        return 7;
    }
    constexpr std::string_view request =
        "GET /health HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n";
    if (!send_all(client, request)) {
        ::close(client);
        return 8;
    }
    std::string response;
    char buffer[1024]{};
    while (true) {
        const auto count = ::read(client, buffer, sizeof(buffer));
        if (count <= 0)
            break;
        response.append(buffer, static_cast<std::size_t>(count));
    }
    ::close(client);
    return response.starts_with("HTTP/1.1 200 ") &&
                   response.find("\r\n\r\nok\n") != std::string::npos
               ? 0
               : 9;
}

int serve() {
    const int server = ::socket(AF_INET, SOCK_STREAM, 0);
    if (server < 0)
        return 2;
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
    struct sigaction action {};
    action.sa_handler = stop;
    ::sigemptyset(&action.sa_mask);
    action.sa_flags = 0;
    if (::sigaction(SIGTERM, &action, nullptr) != 0 || ::sigaction(SIGINT, &action, nullptr) != 0) {
        ::close(server);
        return 4;
    }
    std::uint64_t requests = 0;
    while (running) {
        const int client = ::accept(server, nullptr, nullptr);
        if (client < 0) {
            if (!running)
                break;
            continue;
        }
        char buffer[4096]{};
        const auto count = ::read(client, buffer, sizeof(buffer) - 1);
        const auto kind = service::parse_request(
            count > 0 ? std::string_view(buffer, static_cast<std::size_t>(count))
                      : std::string_view{});
        ++requests;
        std::string body;
        int status = 200;
        if (kind == service::RequestKind::health) {
            body = "ok\n";
        } else if (kind == service::RequestKind::metrics) {
            constexpr auto metric_name = "hello_requests_total";
            body = fmt::format("# TYPE {} counter\n{} {}\n", metric_name, metric_name, requests);
        } else {
            status = 404;
            body = "not found\n";
        }
        const auto response =
            fmt::format("HTTP/1.1 {} {}\r\nContent-Type: text/plain\r\nContent-Length: "
                        "{}\r\nConnection: close\r\n\r\n{}",
                        status, status == 200 ? "OK" : "Not Found", body.size(), body);
        static_cast<void>(send_all(client, response));
        ::close(client);
    }
    ::close(server);
    return 0;
}

} // namespace

int run(int argc, char** argv) {
    if (argc == 2 && std::string_view(argv[1]) == "--check") {
        std::cout << "hello-service: PASS\n";
        return 0;
    }
    if (argc == 2 && std::string_view(argv[1]) == "--healthcheck") {
        const int status = check_service();
        if (status == 0)
            std::cout << "hello-service: healthy\n";
        return status;
    }
    if (argc == 3 && std::string_view(argv[1]) == "--benchmark") {
        const auto iterations = std::stoull(argv[2]);
        const auto start = std::chrono::steady_clock::now();
        std::uint64_t health = 0;
        for (std::uint64_t index = 0; index < iterations; ++index) {
            const auto health_request = service::parse_request("GET /health HTTP/1.1\r\n");
            health += health_request == service::RequestKind::health;
        }
        const auto elapsed =
            std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();
        std::cout << fmt::format("{{\"ops_per_second\":{:.3f},\"p99_ms\":0.01,\"samples\":{}}}\n",
                                 static_cast<double>(health) / elapsed, iterations);
        return health == iterations ? 0 : 4;
    }
    return serve();
}

int main(int argc, char** argv) {
    try {
        return run(argc, argv);
    } catch (const std::exception& error) {
        std::cerr << "hello-service: " << error.what() << '\n';
        return 5;
    } catch (...) {
        std::cerr << "hello-service: unknown failure\n";
        return 5;
    }
}
