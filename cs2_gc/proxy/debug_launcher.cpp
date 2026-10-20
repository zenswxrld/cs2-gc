// Debug-only convenience launcher. Steam owns game startup; no persistent Steam
// settings or autoexec files are edited. Not built/shipped when DEBUG_TOOLS=OFF.
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#include <tlhelp32.h>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <random>
#include <sstream>
#include <string>

namespace
{
int Fail(const wchar_t *text)
{
    MessageBoxW(nullptr, text, L"CS2 GC debug launcher", MB_OK | MB_ICONERROR);
    return 1;
}
bool Running()
{
    const auto snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (snapshot == INVALID_HANDLE_VALUE) return true;
    PROCESSENTRY32W entry{}; entry.dwSize = sizeof(entry);
    bool running = false;
    if (Process32FirstW(snapshot, &entry)) do {
        if (_wcsicmp(entry.szExeFile, L"cs2.exe") == 0) { running = true; break; }
    } while (Process32NextW(snapshot, &entry));
    CloseHandle(snapshot);
    return running;
}
}

int WINAPI wWinMain(HINSTANCE, HINSTANCE, PWSTR, int)
{
    if (Running()) return Fail(L"Close CS2 first, then open this launcher to apply the debug launch options.");
    wchar_t module[32768];
    const auto length = GetModuleFileNameW(nullptr, module, 32768);
    if (!length || length >= 32768) return Fail(L"Could not locate the launcher folder.");
    const auto directory = std::filesystem::path(module).parent_path();
    const auto cfg = directory.parent_path().parent_path() / L"csgo/cfg/cs2_gc_console.cfg";
    if (!std::filesystem::exists(directory / L"cs2.exe") || !std::filesystem::is_directory(cfg.parent_path()))
        return Fail(L"Extract the complete test build into game/bin/win64, beside cs2.exe, before using this launcher.");
    wchar_t steam[32768]; DWORD bytes = sizeof(steam);
    if (RegGetValueW(HKEY_CURRENT_USER, L"Software\\Valve\\Steam", L"SteamExe", RRF_RT_REG_SZ,
                     nullptr, steam, &bytes) != ERROR_SUCCESS || !std::filesystem::is_regular_file(steam))
        return Fail(L"Steam's installed executable could not be found. Open Steam once, then try again.");
    std::random_device random;
    std::ostringstream token;
    for (unsigned i = 0; i < 4; ++i) token << std::hex << std::setfill('0') << std::setw(8) << random();
    const auto nonce = token.str();
    // Prepare before +exec runs. The later background helper reuses this nonce.
    std::ofstream boot(directory / L"cs2_gc_console_boot.txt", std::ios::trunc);
    boot << nonce << '\n'; boot.close();
    std::ofstream config(cfg, std::ios::trunc);
    config << "// Debug launcher generated controls; no persistent autoexec edits.\n"
           << "setinfo cs2_gc_rotation_offset 0\n"
           << "bot_prefix \"\"\n" // no "[BOT]" before bot names (bots that join afterwards)
           << "alias cs2_gc_give_stars \"echo CS2GC_" << nonce << " stars 100\"\n"
           << "alias cs2_gc_give_stars_1000 \"echo CS2GC_" << nonce << " stars 1000\"\n"
           << "alias cs2_gc_force_rotation \"incrementvar cs2_gc_rotation_offset 0 1000000 1; echo CS2GC_" << nonce << " rotate\"\n"
           << "echo Local GC debug commands loaded\n";
    config.close();
    if (!boot || !config) return Fail(L"Could not prepare debug console controls. Check folder write permissions.");
    // A running game locks mounted pak01 files. Prepare all native resources before Steam starts it.
    const auto prepare = directory / L"prepare_native.py";
    if (!std::filesystem::is_regular_file(prepare))
        return Fail(L"Missing prepare_native.py. Extract the complete test ZIP beside this launcher.");
    bool prepared = false;
    for (const auto candidate : {L"py.exe", L"python.exe"}) {
        wchar_t python[32768];
        const auto found = SearchPathW(nullptr, candidate, nullptr, 32768, python, nullptr);
        if (!found || found >= 32768) continue;
        std::wstring prepCommand = L"\"" + std::wstring(python) + L"\"";
        if (_wcsicmp(candidate, L"py.exe") == 0) prepCommand += L" -3";
        prepCommand += L" \"" + prepare.wstring() + L"\" --proxy-dir \"" + directory.wstring() + L"\"";
        STARTUPINFOW prepStartup{}; prepStartup.cb = sizeof(prepStartup);
        PROCESS_INFORMATION prepChild{};
        if (!CreateProcessW(python, prepCommand.data(), nullptr, nullptr, FALSE, CREATE_NO_WINDOW,
                            nullptr, directory.c_str(), &prepStartup, &prepChild)) continue;
        CloseHandle(prepChild.hThread);
        // Preparation is finite; wait in short intervals while keeping the launcher responsive.
        DWORD waited = WAIT_TIMEOUT;
        while ((waited = MsgWaitForMultipleObjects(1, &prepChild.hProcess, FALSE, 1000, QS_ALLINPUT)) == WAIT_TIMEOUT || waited == WAIT_OBJECT_0 + 1) {
            MSG message;
            while (PeekMessageW(&message, nullptr, 0, 0, PM_REMOVE)) {TranslateMessage(&message); DispatchMessageW(&message);}
        }
        DWORD code = 1; GetExitCodeProcess(prepChild.hProcess, &code); CloseHandle(prepChild.hProcess);
        if (code != 0) return Fail(L"Native preparation failed. See cs2_gc_prepare.log beside the launcher. CS2 was not started, so its VPKs remain unlocked.");
        prepared = true; break;
    }
    if (!prepared) return Fail(L"Python 3 was not found. Install it with the Python launcher or PATH option, then try again.");
    std::wstring command = L"\"" + std::wstring(steam) + L"\" -applaunch 730 -insecure -condebug +exec cs2_gc_console";
    STARTUPINFOW startup{}; startup.cb = sizeof(startup);
    PROCESS_INFORMATION child{};
    if (!CreateProcessW(steam, command.data(), nullptr, nullptr, FALSE, 0, nullptr, nullptr, &startup, &child))
        return Fail(L"Steam could not be started with the debug options.");
    CloseHandle(child.hThread); CloseHandle(child.hProcess);
    return 0;
}
