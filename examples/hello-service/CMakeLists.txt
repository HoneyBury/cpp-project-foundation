cmake_minimum_required(VERSION 3.21)
project(
    hello_service
    VERSION 0.3.0
    LANGUAGES CXX
)

option(ENABLE_TESTING "Build tests" ON)
option(ENABLE_FUZZ "Build libFuzzer targets" OFF)
option(FOUNDATION_WARNINGS_AS_ERRORS "Treat project warnings as errors" OFF)
option(FOUNDATION_ENABLE_COVERAGE "Instrument project targets for coverage" OFF)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(fmt CONFIG REQUIRED)
include(cmake/FoundationQuality.cmake)

add_library(hello_core src/request_parser.cpp)
target_include_directories(hello_core PUBLIC include)
target_compile_features(hello_core PUBLIC cxx_std_20)
foundation_enable_warnings(hello_core)
foundation_enable_coverage(hello_core)

add_executable(hello_service src/main.cpp)
set_target_properties(hello_service PROPERTIES OUTPUT_NAME hello-service)
target_link_libraries(hello_service PRIVATE hello_core fmt::fmt)
foundation_enable_warnings(hello_service)
foundation_enable_coverage(hello_service)
# cmake-format: off
set_target_properties(
    hello_service PROPERTIES RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
)
# cmake-format: on

if(ENABLE_TESTING)
    include(CTest)
    enable_testing()
    add_executable(hello_service_tests tests/request_parser_test.cpp)
    target_link_libraries(hello_service_tests PRIVATE hello_core)
    foundation_enable_warnings(hello_service_tests)
    foundation_enable_coverage(hello_service_tests)
    add_test(NAME hello_service.unit COMMAND hello_service_tests)
    set_tests_properties(hello_service.unit PROPERTIES LABELS unit TIMEOUT 30)
endif()

if(ENABLE_FUZZ)
    if(NOT CMAKE_CXX_COMPILER_ID MATCHES "Clang")
        message(FATAL_ERROR "ENABLE_FUZZ requires Clang")
    endif()
    add_executable(fuzz_request_parser fuzz/fuzz_request_parser.cpp)
    # cmake-format: off
    target_compile_options(
        hello_core PRIVATE -fsanitize=fuzzer-no-link,address,undefined
    )
    # cmake-format: on
    target_link_libraries(fuzz_request_parser PRIVATE hello_core)
    target_compile_options(fuzz_request_parser PRIVATE -fsanitize=fuzzer,address,undefined)
    target_link_options(fuzz_request_parser PRIVATE -fsanitize=fuzzer,address,undefined)
    foundation_enable_warnings(fuzz_request_parser)
    set_target_properties(
        fuzz_request_parser PROPERTIES RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    )
endif()

install(TARGETS hello_service RUNTIME DESTINATION bin)
