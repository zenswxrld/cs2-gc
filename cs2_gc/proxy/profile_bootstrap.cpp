// Read-only first-run Steam handshake. Sends only Hello, Store-data and mission-schema
// requests already used by the target client. No purchase/equip/tool requests are forwarded.
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#include "cs2_gc/gc_handshake.h"
#include "cs2_gc/gc_msg_ids.h"
#include "cs2_gc/message_queue.h"
#include "cs2_gc/protobuf.h"
#include "cs2_gc/replay.h"
#include <chrono>
#include <filesystem>
#include <iostream>
#include <string>
#include <vector>

using namespace cs2_gc;
class SteamGameCoordinatorInterface
{
public:
    virtual GCResult SendMessage(std::uint32_t,const void *,std::uint32_t)=0;
    virtual bool IsMessageAvailable(std::uint32_t *)=0;
    virtual GCResult RetrieveMessage(std::uint32_t *,void *,std::uint32_t,std::uint32_t *)=0;
};

int wmain(int argc,wchar_t **argv)
{
    if(argc!=3){std::cerr<<"Expected game/bin/win64 and client version.\n";return 1;}
    const std::filesystem::path directory=std::filesystem::absolute(argv[1]);
    std::uint32_t version=0;
    try{
        const std::wstring text=argv[2];std::size_t used=0;
        const auto number=std::stoull(text,&used);
        if(used!=text.size()||!number||number>UINT32_MAX)return 1;
        version=static_cast<std::uint32_t>(number);
    }catch(...){return 1;}
    SetCurrentDirectoryW(directory.c_str());
    SetEnvironmentVariableW(L"SteamAppId",L"730");
    SetEnvironmentVariableW(L"SteamGameId",L"730");
    const auto module=LoadLibraryExW((directory/L"steam_api64_real.dll").c_str(),nullptr,LOAD_WITH_ALTERED_SEARCH_PATH);
    if(!module){std::cerr<<"Original Steam API library could not load: "<<GetLastError()<<"\n";return 1;}
    // SteamAPI_Init is inline in modern SDK headers, not a DLL export.
    // Valve's dynamic-loading entry point returns ESteamAPIInitResult (0 = OK)
    // and writes a SteamErrMsg (1024 chars), rather than returning bool.
    using SteamErrorMessage=char[1024];
    const auto init=reinterpret_cast<int(__cdecl*)(SteamErrorMessage*)>(
        GetProcAddress(module,"SteamAPI_InitFlat"));
    const auto shutdown=reinterpret_cast<void(__cdecl*)()>(GetProcAddress(module,"SteamAPI_Shutdown"));
    const auto callbacks=reinterpret_cast<void(__cdecl*)()>(GetProcAddress(module,"SteamAPI_RunCallbacks"));
    const auto getUser=reinterpret_cast<int(__cdecl*)()>(GetProcAddress(module,"SteamAPI_GetHSteamUser"));
    const auto find=reinterpret_cast<void*(__cdecl*)(int,const char*)>(
        GetProcAddress(module,"SteamInternal_FindOrCreateUserInterface"));
    const auto getSteamId=reinterpret_cast<std::uint64_t(__cdecl*)(void*)>(
        GetProcAddress(module,"SteamAPI_ISteamUser_GetSteamID"));
    if(!init||!shutdown||!callbacks||!getUser||!find||!getSteamId){
        std::cerr<<"Unsupported Steam API exports:";
        if(!init)std::cerr<<" SteamAPI_InitFlat";
        if(!shutdown)std::cerr<<" SteamAPI_Shutdown";
        if(!callbacks)std::cerr<<" SteamAPI_RunCallbacks";
        if(!getUser)std::cerr<<" SteamAPI_GetHSteamUser";
        if(!find)std::cerr<<" SteamInternal_FindOrCreateUserInterface";
        if(!getSteamId)std::cerr<<" SteamAPI_ISteamUser_GetSteamID";
        std::cerr<<"\n";return 1;
    }
    bool initialized=false;
    SteamErrorMessage initError{};
    int initResult=-1;
    for(unsigned attempt=0;attempt<30&&!initialized;++attempt){
        initError[0]='\0';
        initResult=init(&initError);
        initialized=initResult==0;
        if(!initialized)Sleep(1000);
    }
    if(!initialized){std::cerr<<"Steam initialization failed (result="<<initResult<<"): "<<initError<<"\n";return 1;}
    // Valve documents GC access through ISteamClient::GetISteamGenericInterface.
    // Use its exported flat wrapper rather than assuming a vtable slot.
    const auto create=reinterpret_cast<void*(__cdecl*)(const char*)>(
        GetProcAddress(module,"SteamInternal_CreateInterface"));
    const auto getPipe=reinterpret_cast<int(__cdecl*)()>(GetProcAddress(module,"SteamAPI_GetHSteamPipe"));
    const auto generic=reinterpret_cast<void*(__cdecl*)(void*,int,int,const char*)>(
        GetProcAddress(module,"SteamAPI_ISteamClient_GetISteamGenericInterface"));
    void *client=create?create("SteamClient023"):nullptr;
    auto *gc=client&&getPipe&&generic?static_cast<SteamGameCoordinatorInterface*>(
        generic(client,getUser(),getPipe(),"SteamGameCoordinator001")):nullptr;
    void *user=find(getUser(),"SteamUser023");
    const std::uint64_t steamId=user?getSteamId(user):0;
    if(!gc||!steamId){std::cerr<<"Steam GC/user interface unavailable.\n";shutdown();return 1;}
    const auto replayPath=directory/L"cs2_gc_replay";
    const auto existing=ReplayStore::LoadDirectory(replayPath);
    if(const auto *welcome=existing.Find(gc_msg::EGCBaseClientMsg::k_EMsgGCClientWelcome)){
        const auto decoded=DecodeClientWelcome(*welcome);
        if(!decoded||decoded->outOfDateCaches.empty()){
            std::cerr<<"Existing welcome is invalid; refusing to overwrite saved account files.\n";shutdown();return 1;
        }
        for(const auto &cache:decoded->outOfDateCaches)
            if(cache.owner.id&&cache.owner.id!=steamId){
                std::cerr<<"Saved welcome belongs to a different Steam account. Use a separate mod folder for each account.\n";
                shutdown();return 1;
            }
    }
    auto send=[&](std::uint32_t id,std::span<const std::uint8_t> body){
        std::vector<std::uint8_t> frame;
        if(WriteProtobufFrame(id,{},body,frame)!=FrameError::None)return false;
        return gc->SendMessage(id|ProtobufMask,frame.data(),static_cast<std::uint32_t>(frame.size()))==GCResult::OK;
    };
    PbWriter hello;hello.Varint(1,version);hello.Varint(3,0);hello.Varint(4,0);hello.Varint(9,0);
    const auto started=std::chrono::steady_clock::now();
    auto nextHello=started;
    auto readyAt=started;
    bool haveWelcome=false,haveStore=false,requestedData=false;
    constexpr std::uint32_t MissionRequest=9225; // CMsgRecurringMissionSchema request in target descriptors
    constexpr std::uint32_t MissionResponse=9226;
    for(;;){
        const auto now=std::chrono::steady_clock::now();
        if(now-started>std::chrono::seconds(65))break;
        if(!haveWelcome&&now>=nextHello){
            send(gc_msg::EGCBaseClientMsg::k_EMsgGCClientHello,hello.bytes());
            nextHello=now+std::chrono::seconds(5);
        }
        callbacks();
        std::uint32_t size=0;
        for(unsigned count=0;count<32&&gc->IsMessageAvailable(&size);++count){
            if(!size||size>ReplayStore::MaxBodyBytes+1024){
                std::cerr<<"Unexpected GC frame size.\n";shutdown();return 1;
            }
            std::vector<std::uint8_t> bytes(size);std::uint32_t type=0,received=0;
            if(gc->RetrieveMessage(&type,bytes.data(),size,&received)!=GCResult::OK)continue;
            FrameView frame;
            if(received>size||ReadProtobufFrame(type,{bytes.data(),received},frame)!=FrameError::None)continue;
            const auto id=type&~ProtobufMask;
            if(id==gc_msg::EGCBaseClientMsg::k_EMsgGCClientWelcome){
                const auto welcome=DecodeClientWelcome(frame.body);
                bool own=false;
                if(welcome)for(const auto &cache:welcome->outOfDateCaches)
                    own|=cache.owner.id==steamId&&!cache.types.empty();
                if(!own){std::cerr<<"Steam did not return a usable welcome for this account/build.\n";continue;}
                ReplayStore::SaveIfMissing(replayPath,id,frame.body);
                haveWelcome=true;
            }else if(id==gc_msg::EGCItemMsg::k_EMsgGCStoreGetUserDataResponse){
                // Require the actual compressed price sheet, not an error/empty response.
                PbReader reader(frame.body);PbField field;bool sheet=false;
                while(reader.Next(field))
                    if(field.number==8&&field.wire==2&&field.bytes.size()>=17&&
                       field.bytes[0]=='L'&&field.bytes[1]=='Z'&&field.bytes[2]=='M'&&field.bytes[3]=='A')sheet=true;
                if(sheet&&!reader.Failed()){
                    ReplayStore::SaveIfMissing(replayPath,id,frame.body);haveStore=true;
                }
            }else if(id==MissionResponse&&!frame.body.empty()){
                ReplayStore::SaveIfMissing(replayPath,id,frame.body);
            }
            if(haveWelcome&&haveStore)readyAt=now;
        }
        if(haveWelcome&&!requestedData){
            send(gc_msg::EGCItemMsg::k_EMsgGCStoreGetUserData,{});
            send(MissionRequest,{});
            requestedData=true;
        }
        if(haveWelcome&&haveStore&&now-readyAt>std::chrono::seconds(2))break;
        Sleep(50);
    }
    shutdown();
    if(!haveWelcome||!haveStore){
        std::cerr<<"Steam handshake timed out (welcome="<<haveWelcome<<", store="<<haveStore
                 <<"). Ensure Steam is online and the account owns CS2. No inventory was changed.\n";return 1;
    }
    std::cout<<"Own-account welcome and Store data saved locally. Profile initialization complete.\n";
    return 0;
}
