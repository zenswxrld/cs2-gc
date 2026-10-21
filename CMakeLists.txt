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
    cs2_gc/src/armory.cpp
    cs2_gc/src/armory_catalog.cpp
    cs2_gc/src/case_opening.cpp
    cs2_gc/src/econ_item.cpp
    cs2_gc/src/gc_endpoint.cpp
    cs2_gc/src/gc_handshake.cpp
    cs2_gc/src/gc_summary.cpp
    cs2_gc/src/protobuf.cpp
    cs2_gc/src/protobuf_dump.cpp
    cs2_gc/src/replay.cpp
    cs2_gc/src/proxy_support.cpp
    cs2_gc/src/item_sales.cpp
    cs2_gc/src/inventory.cpp
    cs2_gc/src/keyvalues.cpp
    cs2_gc/src/live_inventory.cpp
    cs2_gc/src/schema.cpp
    cs2_gc/src/trade_up.cpp
    cs2_gc/src/terminal.cpp
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
        add_test(NAME cs2_local_results_and_sales COMMAND ${Python3_EXECUTABLE} -m unittest discover -s tests -p test_local_results_and_sales.py -v)
        set_tests_properties(cs2_local_results_and_sales PROPERTIES WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})
        add_test(NAME cs2_native_ui COMMAND ${Python3_EXECUTABLE} -m unittest discover -s tests -p test_native_ui.py -v)
        add_test(NAME cs2_native_bot_names COMMAND ${Python3_EXECUTABLE} -m unittest discover -s tests -p test_native_bot_names.py -v)
        set_tests_properties(cs2_native_bot_names PROPERTIES WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})
        add_test(NAME cs2_skip_key_select COMMAND ${Python3_EXECUTABLE} -m unittest discover -s tests -p test_skip_key_select.py -v)
        set_tests_properties(cs2_skip_key_select PROPERTIES WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})
        add_test(NAME cs2_endmatch_stock COMMAND ${Python3_EXECUTABLE} -m unittest discover -s tests -p test_endmatch_stock.py -v)
        set_tests_properties(cs2_endmatch_stock PROPERTIES WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})
        add_test(NAME cs2_kv3 COMMAND ${Python3_EXECUTABLE} -m unittest discover -s tests -p test_kv3.py -v)
        set_tests_properties(cs2_kv3 PROPERTIES WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})
        add_test(NAME cs2_native_finishes COMMAND ${Python3_EXECUTABLE} -m unittest discover -s tests -p test_native_finishes.py -v)
        add_test(NAME cs2_native_gloves COMMAND ${Python3_EXECUTABLE} -m unittest discover -s tests -p test_native_gloves.py -v)
        set_tests_properties(cs2_native_finishes PROPERTIES WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(cs2_native_gloves PROPERTIES WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})
        add_test(NAME cs2_native_knife_reel COMMAND ${Python3_EXECUTABLE} -m unittest discover -s tests -p test_native_knife_reel.py -v)
        set_tests_properties(cs2_native_knife_reel PROPERTIES WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})
        add_test(NAME cs2_reset_profile COMMAND ${Python3_EXECUTABLE} -m unittest discover -s tests -p test_reset_profile.py -v)
        set_tests_properties(cs2_reset_profile PROPERTIES WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})
        add_test(NAME cs2_vpk_pack COMMAND ${Python3_EXECUTABLE} -m unittest discover -s tests -p test_vpk_pack.py -v)
        set_tests_properties(cs2_vpk_pack PROPERTIES WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(cs2_native_ui PROPERTIES WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})
        add_test(NAME cs2_armory_rotation COMMAND ${Python3_EXECUTABLE} -m unittest discover -s tests -p test_armory_rotation_catalog.py -v)
        set_tests_properties(cs2_armory_rotation PROPERTIES WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})
        add_test(NAME cs2_native_tradeups COMMAND ${Python3_EXECUTABLE} -m unittest discover -s tests -p test_native_tradeups.py -v)
        set_tests_properties(cs2_native_tradeups PROPERTIES WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})
        add_test(NAME cs2_rewards_runtime COMMAND ${Python3_EXECUTABLE} -m unittest discover -s tests -p test_rewards_runtime.py -v)
        set_tests_properties(cs2_rewards_runtime PROPERTIES WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})
        add_test(NAME cs2_gameplay_options COMMAND ${Python3_EXECUTABLE} -m unittest discover -s tests -p test_gameplay_options.py -v)
        set_tests_properties(cs2_gameplay_options PROPERTIES WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})
        add_test(NAME cs2_gsi_rewards COMMAND ${Python3_EXECUTABLE} -m unittest discover -s tests -p test_gsi_rewards.py -v)
        set_tests_properties(cs2_gsi_rewards PROPERTIES WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})
        add_test(NAME cs2_test_item_grants COMMAND ${Python3_EXECUTABLE} -m unittest discover -s tests -p test_test_item_grants.py -v)
        set_tests_properties(cs2_test_item_grants PROPERTIES WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})
        add_test(NAME cs2_client_inspection
            COMMAND ${Python3_EXECUTABLE} -m unittest discover -s tests -p test_inspect_cs2.py -v)
        set_tests_properties(cs2_client_inspection PROPERTIES WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})
        add_test(NAME cs2_gc_protocol_extraction
            COMMAND ${Python3_EXECUTABLE} -m unittest discover -s tests -p test_extract_gc_protocol.py -v)
        set_tests_properties(cs2_gc_protocol_extraction PROPERTIES WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})
        add_test(NAME cs2_price_sheet_tool
            COMMAND ${Python3_EXECUTABLE} -m unittest discover -s tests -p test_price_sheet.py -v)
        set_tests_properties(cs2_price_sheet_tool PROPERTIES WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})
        add_test(NAME cs2_inventory_item_tool
            COMMAND ${Python3_EXECUTABLE} -m unittest discover -s tests -p test_inventory_item.py -v)
        set_tests_properties(cs2_inventory_item_tool PROPERTIES WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})
        add_test(NAME cs2_proxy_def_generation
            COMMAND ${Python3_EXECUTABLE} -m unittest discover -s tests -p test_make_proxy_def.py -v)
        set_tests_properties(cs2_proxy_def_generation PROPERTIES WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})
    endif()
endif()

# Diagnostic stand-in steam_api64.dll (Windows only, off by default). Needs a .def generated
# from the game's own steam_api64.dll with tools/make_proxy_def.py.
option(CS2_GC_BUILD_PROXY "Build the diagnostic steam_api64.dll stand-in" OFF)
option(CS2_GC_DEBUG_TOOLS "Enable test console controls and build the automatic debug launcher" OFF)
if(CS2_GC_BUILD_PROXY)
    if(NOT WIN32)
        message(FATAL_ERROR "CS2_GC_BUILD_PROXY is Windows only")
    endif()
    set(CS2_GC_PROXY_DEF "" CACHE FILEPATH "Output of tools/make_proxy_def.py")
    if(NOT EXISTS "${CS2_GC_PROXY_DEF}")
        message(FATAL_ERROR "Set CS2_GC_PROXY_DEF to the generated .def file")
    endif()
    file(READ "${CS2_GC_PROXY_DEF}" PROXY_EXPORTS)
    foreach(SERVER_EXPORT SteamGameServer_RunCallbacks SteamInternal_FindOrCreateGameServerInterface)
        if(NOT PROXY_EXPORTS MATCHES "${SERVER_EXPORT}" OR PROXY_EXPORTS MATCHES "${SERVER_EXPORT}[ \t]*=")
            message(FATAL_ERROR "Regenerate the proxy .def with tools/make_proxy_def.py: ${SERVER_EXPORT} must be intercepted for bot servers")
        endif()
    endforeach()
    add_library(cs2_gc_proxy SHARED cs2_gc/proxy/steam_api_proxy.cpp cs2_gc/proxy/viewmodel_range.cpp "${CS2_GC_PROXY_DEF}")
    set_target_properties(cs2_gc_proxy PROPERTIES OUTPUT_NAME steam_api64 PREFIX "")
    target_link_libraries(cs2_gc_proxy PRIVATE cs2_gc_core)
    if(CS2_GC_DEBUG_TOOLS)
        target_compile_definitions(cs2_gc_proxy PRIVATE CS2_GC_DEBUG_TOOLS=1)
        add_executable(cs2_gc_debug WIN32 cs2_gc/proxy/debug_launcher.cpp)
        target_link_libraries(cs2_gc_debug PRIVATE advapi32)
        if(NOT MSVC)
            target_link_options(cs2_gc_debug PRIVATE -static -municode)
        endif()
    endif()
    add_custom_command(TARGET cs2_gc_proxy POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E copy_if_different ${CMAKE_CURRENT_SOURCE_DIR}/data/gold_pools.txt $<TARGET_FILE_DIR:cs2_gc_proxy>/gold_pools.txt)
    if(NOT MSVC)
        target_link_options(cs2_gc_proxy PRIVATE -static)
    endif()
endif()
