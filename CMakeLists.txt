cmake_minimum_required(VERSION 3.20)
project(cs2_gc VERSION 0.1.0 LANGUAGES CXX)

if(NOT CMAKE_SIZEOF_VOID_P EQUAL 8)
    message(FATAL_ERROR "The CS2 port requires a 64-bit toolchain. Use -A x64 with Visual Studio.")
endif()

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
include(CTest)
find_package(Threads REQUIRED)

add_library(cs2_gc_core STATIC
    cs2_gc/src/armory_catalog.cpp
    cs2_gc/src/case_opening.cpp
    cs2_gc/src/inventory.cpp
    cs2_gc/src/keyvalues.cpp
    cs2_gc/src/schema.cpp
    cs2_gc/src/wire.cpp
    cs2_gc/src/message_queue.cpp
    cs2_gc/src/progression.cpp)
target_include_directories(cs2_gc_core PUBLIC cs2_gc/include)
target_link_libraries(cs2_gc_core PUBLIC Threads::Threads)
if(MSVC)
    target_compile_options(cs2_gc_core PRIVATE /W4 /WX /permissive-)
else()
    target_compile_options(cs2_gc_core PRIVATE -Wall -Wextra -Wpedantic -Werror)
endif()

if(BUILD_TESTING)
    add_executable(cs2_gc_core_tests tests/core_tests.cpp)
    target_link_libraries(cs2_gc_core_tests PRIVATE cs2_gc_core)
    add_test(NAME cs2_gc_core COMMAND cs2_gc_core_tests)

    find_package(Python3 COMPONENTS Interpreter)
    if(Python3_FOUND)
        add_test(NAME cs2_client_inspection
            COMMAND ${Python3_EXECUTABLE} -m unittest discover -s tests -p test_inspect_cs2.py -v)
        set_tests_properties(cs2_client_inspection PROPERTIES WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})
        add_test(NAME cs2_gc_protocol_extraction
            COMMAND ${Python3_EXECUTABLE} -m unittest discover -s tests -p test_extract_gc_protocol.py -v)
        set_tests_properties(cs2_gc_protocol_extraction PROPERTIES WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})
    endif()
endif()
