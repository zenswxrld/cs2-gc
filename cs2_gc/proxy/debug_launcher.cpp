// Complete-ZIP launcher. Prepare and start the CS2 executable beside the mod,
// including copies outside Steam's managed library. Never use Steam -applaunch.
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#include <tlhelp32.h>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iterator>
#include <random>
#include <sstream>
#include <string>

namespace
{
int Fail(const std::wstring &text)
{
    MessageBoxW(nullptr,text.c_str(),L"CS2 GC launcher",MB_OK|MB_ICONERROR);
    return 1;
}
bool Running(const wchar_t *name)
{
    const auto snapshot=CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS,0);
    if(snapshot==INVALID_HANDLE_VALUE)return true;
    PROCESSENTRY32W entry{};entry.dwSize=sizeof(entry);
    bool running=false;
    if(Process32FirstW(snapshot,&entry))do{
        if(_wcsicmp(entry.szExeFile,name)==0){running=true;break;}
    }while(Process32NextW(snapshot,&entry));
    CloseHandle(snapshot);
    return running;
}
std::wstring Quote(const std::filesystem::path &path)
{
    return L"\""+path.wstring()+L"\"";
}
std::wstring Detail(const std::filesystem::path &path)
{
    std::ifstream file(path,std::ios::binary);
    const std::string text((std::istreambuf_iterator<char>(file)),{});
    if(text.empty()||text.size()>8192)return L"See cs2_gc_prepare.log and cs2_gc_launcher.log in game/bin/win64.";
    const int length=MultiByteToWideChar(CP_UTF8,0,text.data(),static_cast<int>(text.size()),nullptr,0);
    std::wstring wide(static_cast<std::size_t>(length),L'\0');
    MultiByteToWideChar(CP_UTF8,0,text.data(),static_cast<int>(text.size()),wide.data(),length);
    return wide;
}
DWORD Wait(HANDLE process)
{
    for(;;){
        const DWORD result=MsgWaitForMultipleObjects(1,&process,FALSE,1000,QS_ALLINPUT);
        if(result==WAIT_OBJECT_0)break;
        if(result==WAIT_FAILED)return 1;
        MSG message;
        while(PeekMessageW(&message,nullptr,0,0,PM_REMOVE)){TranslateMessage(&message);DispatchMessageW(&message);}
    }
    DWORD code=1;GetExitCodeProcess(process,&code);return code;
}
}

int WINAPI wWinMain(HINSTANCE,HINSTANCE,PWSTR,int)
{
    const auto mutex=CreateMutexW(nullptr,TRUE,L"Local\\CS2GC_LaunchPreparation");
    if(!mutex||GetLastError()==ERROR_ALREADY_EXISTS)return Fail(L"Another CS2 GC launcher is already preparing the game.");
    if(Running(L"cs2.exe"))return Fail(L"Close CS2 first, then launch CS2 GC again.");
    wchar_t module[32768];
    const auto length=GetModuleFileNameW(nullptr,module,32768);
    if(!length||length>=32768)return Fail(L"Could not locate this launcher.");
    auto directory=std::filesystem::path(module).parent_path();
    if(!std::filesystem::is_regular_file(directory/L"cs2.exe"))
        directory/=L"game/bin/win64";
    const auto game=directory.parent_path().parent_path();
    const auto cfg=game/L"csgo/cfg/cs2_gc_console.cfg";
    if(!std::filesystem::is_regular_file(directory/L"cs2.exe")||!std::filesystem::is_directory(cfg.parent_path()))
        return Fail(L"Extract the complete ZIP into the CS2 root folder containing game, then open Launch CS2 GC.exe.");
    const auto python=directory/L"cs2_gc_python/python.exe";
    const auto setup=directory/L"launch_setup.py";
    if(!std::filesystem::is_regular_file(python)||!std::filesystem::is_regular_file(setup))
        return Fail(L"The bundled runtime or setup helper is missing. Extract the COMPLETE ZIP; no separate Python installation is needed.");
    wchar_t steam[32768];DWORD bytes=sizeof(steam);
    if(RegGetValueW(HKEY_CURRENT_USER,L"Software\\Valve\\Steam",L"SteamExe",RRF_RT_REG_SZ,
                   nullptr,steam,&bytes)!=ERROR_SUCCESS||!std::filesystem::is_regular_file(steam))
        return Fail(L"Steam was not found. Install Steam and sign in to the account that owns CS2.");
    if(!Running(L"steam.exe")){
        std::wstring command=Quote(steam)+L" -silent";
        STARTUPINFOW startup{};startup.cb=sizeof(startup);startup.dwFlags=STARTF_USESHOWWINDOW;startup.wShowWindow=SW_HIDE;
        PROCESS_INFORMATION child{};
        if(!CreateProcessW(steam,command.data(),nullptr,nullptr,FALSE,CREATE_NO_WINDOW,nullptr,nullptr,&startup,&child))
            return Fail(L"Steam could not start. Open Steam and sign in, then try again.");
        WaitForInputIdle(child.hProcess,20000);
        CloseHandle(child.hThread);CloseHandle(child.hProcess);
    }
    // Bind this process and its children to CS2 without redirecting to another install.
    SetEnvironmentVariableW(L"SteamAppId",L"730");
    SetEnvironmentVariableW(L"SteamGameId",L"730");
    std::random_device random;std::ostringstream token;
    for(unsigned i=0;i<4;++i)token<<std::hex<<std::setfill('0')<<std::setw(8)<<random();
    const auto nonce=token.str();
    std::ofstream boot(directory/L"cs2_gc_console_boot.txt",std::ios::trunc);boot<<nonce<<'\n';boot.close();
    std::error_code logError;
    const auto logSize=std::filesystem::file_size(game/L"csgo/console.log",logError);
    std::ofstream careBoot(directory/L"cs2_gc_care_boot.txt",std::ios::trunc);
    careBoot<<nonce<<' '<<(logError?0:logSize)<<'\n';careBoot.close();
    std::ofstream config(cfg,std::ios::trunc);
    config<<"// CS2 GC launch session; user autoexec is untouched.\n"
          <<"setinfo cs2_gc_session_code "<<nonce<<"\nsetinfo cs2_gc_rotation_offset 0\nbot_prefix \"\"\n"
          <<"exec cs2_gc_premier_bots\n"
          <<"setinfo cs2gc_"<<nonce<<"_s100 0\nsetinfo cs2gc_"<<nonce<<"_s1000 0\nsetinfo cs2gc_"<<nonce<<"_rot 0\n"
          <<"alias cs2_gc_give_stars \"incrementvar cs2gc_"<<nonce<<"_s100 0 1000000 1\"\n"
          <<"alias cs2_gc_give_stars_1000 \"incrementvar cs2gc_"<<nonce<<"_s1000 0 1000000 1\"\n"
          <<"alias cs2_gc_force_rotation \"incrementvar cs2_gc_rotation_offset 0 1000000 1; incrementvar cs2gc_"<<nonce<<"_rot 0 1000000 1\"\n";
    config.close();
    if(!boot||!careBoot||!config)return Fail(L"Could not write launch settings. Extract into a writable game folder.");
    std::wstring command=Quote(python)+L" -B "+Quote(setup)+L" --proxy-dir "+Quote(directory);
    STARTUPINFOW startup{};startup.cb=sizeof(startup);
    PROCESS_INFORMATION child{};
    if(!CreateProcessW(python.c_str(),command.data(),nullptr,nullptr,FALSE,CREATE_NEW_CONSOLE,
                      nullptr,directory.c_str(),&startup,&child))
        return Fail(L"The bundled Python runtime could not start. Re-extract the complete ZIP.");
    CloseHandle(child.hThread);
    const auto code=Wait(child.hProcess);CloseHandle(child.hProcess);
    if(code!=0)return Fail(Detail(directory/L"cs2_gc_launch_error.txt"));
    const auto executable=directory/L"cs2.exe";
    command=Quote(executable)+L" -insecure -condebug +exec cs2_gc_console";
    child={};startup={};startup.cb=sizeof(startup);
    if(!CreateProcessW(executable.c_str(),command.data(),nullptr,nullptr,FALSE,0,
                      nullptr,directory.c_str(),&startup,&child))
        return Fail(L"CS2 could not start from this folder. Windows error "+std::to_wstring(GetLastError())+L".");
    CloseHandle(child.hThread);
    if(WaitForSingleObject(child.hProcess,3000)==WAIT_OBJECT_0){
        DWORD exitCode=0;GetExitCodeProcess(child.hProcess,&exitCode);CloseHandle(child.hProcess);
        std::wostringstream message;
        message<<L"CS2 closed during startup (exit 0x"<<std::hex<<exitCode
               <<L"). See game/bin/win64/cs2_gc_log.txt. The launcher started this copy directly.";
        return Fail(message.str());
    }
    CloseHandle(child.hProcess);
    ReleaseMutex(mutex);CloseHandle(mutex);
    return 0;
}
