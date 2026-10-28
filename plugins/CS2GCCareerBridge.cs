// Local, factual event counters. Star awards are owned by the rewards helper.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Runtime.Versioning;
using System.Drawing;
using CounterStrikeSharp.API;
using CounterStrikeSharp.API.Core;
using CounterStrikeSharp.API.Modules.Timers;
using CounterStrikeSharp.API.Modules.Utils;

[assembly: TargetFramework(".NETCoreApp,Version=v10.0", FrameworkDisplayName=".NET 10.0")]
public sealed class CS2GCCareerBridge : BasePlugin
{
    public override string ModuleName => "CS2 GC Career Bridge";
    public override string ModuleVersion => "1.0.0";
    public override string ModuleAuthor => "CS2 GC";
    public override string ModuleDescription => "Local combat and utility achievement counters";
    private readonly string session = Guid.NewGuid().ToString("N");
    private readonly Dictionary<string,Dictionary<string,long>> players = new();
    private readonly Dictionary<(int,uint),float> flashes = new();
    private readonly Dictionary<uint,int> deaths = new();
    private string directory = "", nonce = "";
    private long sequence;
    private bool dirty = true, ended;
    private CChicken? chicken;
    private string chickenBreed="off",localOwner="",petVersion="";
    private int petStage;
    private uint petSeed;
    private ulong petInventoryId;
    private uint petAccessory;
    private CDynamicProp? hat;
    private bool unloading;
    private string chatMode="normal";
    private float lastChat=-1000;
    private int chatEpoch;
    private readonly Dictionary<uint,float> botLastChat=new();
    private static readonly string[] HatModels={"helmet","armor_helmet","glasses","nose_glasses","banana","party","sprout","alien","top_hat","wizard_hat"};
    public override void Load(bool hotReload)
    {
        directory=Path.GetFullPath(Path.Combine(Server.GameDirectory,"..","bin","win64"));
        RegisterListener<Listeners.OnServerPrecacheResources>(manifest=>
        {
            foreach(var model in new[]{"chick","chicken","chicken_silkie","chicken_polish"})manifest.AddResource("models/chicken/"+model+".vmdl");
            foreach(var model in HatModels)manifest.AddResource("models/photobooth/silly_hats/"+model+".vmdl");
        });
        RegisterEventHandler<EventPlayerBlind>(OnBlind);
        RegisterEventHandler<EventPlayerDeath>(OnDeath);
        var chatFile=Path.Combine(directory,"cs2_gc_bot_chat.txt");
        if(File.Exists(chatFile)){var mode=File.ReadAllText(chatFile).Trim();if(new[]{"off","less","normal","more"}.Contains(mode))chatMode=mode;}
        RegisterListener<Listeners.OnMapStart>(name=>{chatEpoch++;lastChat=-1000;botLastChat.Clear();});
        RegisterEventHandler<EventRoundStart>((e,i)=>{ended=false;flashes.Clear();deaths.Clear();chatEpoch++;Chat(null,.25f,"gl hf","let's have a good round","ready when you are");return HookResult.Continue;});
        RegisterEventHandler<EventBombPlanted>((e,i)=>{Chat(null,.45f,"bomb's down, watch the angles","time to hold the site","play the bomb");return HookResult.Continue;});
        RegisterEventHandler<EventBombDefused>((e,i)=>{Chat(null,.5f,"nice defuse","that was close","good retake");return HookResult.Continue;});
        RegisterEventHandler<EventRoundEnd>((e,i)=>{Chat(null,.35f,"gg, next round","reset and go again","good round");return HookResult.Continue;});
        RegisterEventHandler<EventCsWinPanelMatch>((e,i)=>{Chat(null,1f,"gg wp","good game everyone","gg, that was fun");ended=true;Flush();return HookResult.Continue;});
        AddTimer(1,Flush,TimerFlags.REPEAT);
        AddCommand("css_bot_chat","Bot chat reactions: off, less, normal or more",(player,command)=>
        {
            if(!Human(player)||player!.SteamID.ToString()!=localOwner)return;
            var mode=command.ArgCount>1?command.GetArg(1):"";
            if(!new[]{"off","less","normal","more"}.Contains(mode)){player.PrintToChat("[Bots] css_bot_chat off | less | normal | more (current: "+chatMode+")");return;}
            chatMode=mode;chatEpoch++;File.WriteAllText(chatFile,mode+"\n");player.PrintToChat("[Bots] Chat reactions: "+mode);
        });
        AddCommand("css_chicken","Select an owned chicken by inventory ID, or off; optional accessory definition",(player,command)=>
        {
            if (!Human(player) || player!.SteamID.ToString()!=localOwner) return;
            var requested=command.ArgCount>1?command.GetArg(1):"";
            ulong id=0;uint accessory=uint.MaxValue;
            if((requested!="off"&&!ulong.TryParse(requested,out id))||(command.ArgCount>2&&!uint.TryParse(command.GetArg(2),out accessory)))
            {player.PrintToChat("[Chickens] Use css_chicken <inventory ID> [accessory definition], or css_chicken off.");return;}
            var path=Path.Combine(directory,"cs2_gc_pet_request.txt");
            File.WriteAllText(path+".tmp",Environment.ProcessId+" "+DateTimeOffset.UtcNow.ToUnixTimeMilliseconds()+" "+id+" "+accessory+"\n");
            File.Move(path+".tmp",path,true);player.PrintToChat("[Chickens] Selection sent to your local inventory.");
        });
        Flush();
    }
    public override void Unload(bool hotReload) { unloading=true;RemoveChicken();Flush(); }
    private void Chat(CCSPlayerController? preferred,float chance,params string[] lines)
    {
        if(unloading||chatMode=="off"||lines.Length==0)return;
        var owner=Utilities.GetPlayers().FirstOrDefault(p=>Human(p)&&p.SteamID.ToString()==localOwner);
        // Authored bot reactions only in this player's local match.
        if(owner==null||Utilities.GetPlayers().Count(p=>Human(p))!=1)return;
        float now=Server.CurrentTime,gap=chatMode=="less"?35:chatMode=="more"?12:22;
        if(now-lastChat<gap||Random.Shared.NextDouble()>chance*(chatMode=="more"?1.5:chatMode=="less"?.6:1))return;
        var bots=Utilities.GetPlayers().Where(p=>p.IsValid&&p.IsBot&&!p.IsHLTV&&(p.TeamNum==2||p.TeamNum==3)).ToArray();
        var bot=preferred?.IsValid==true&&preferred.IsBot?preferred:bots.OrderBy(p=>Random.Shared.Next()).FirstOrDefault();
        if(bot==null)return;
        if(botLastChat.TryGetValue(bot.Index,out float last)&&now-last<55)return;
        lastChat=now;botLastChat[bot.Index]=now;
        string name=new string(bot.PlayerName.Where(c=>!char.IsControl(c)&&c!='\x7f').Take(40).ToArray());
        string text=lines[Random.Shared.Next(lines.Length)];int epoch=chatEpoch;uint index=bot.Index;
        AddTimer(1.4f+(float)Random.Shared.NextDouble()*1.8f,()=>
        {
            if(unloading||epoch!=chatEpoch||chatMode=="off"||!owner.IsValid||!bot.IsValid||!bot.IsBot||bot.Index!=index)return;
            owner.PrintToChat("\x01\x0b"+name+"\x01: "+text);
        },TimerFlags.STOP_ON_MAPCHANGE);
    }
    private void RemoveChicken() {if(hat?.IsValid==true)hat.Remove();hat=null;if(chicken?.IsValid==true)chicken.Remove();chicken=null;}
    private void FollowChicken()
    {
        if(unloading)return;
        var player=Utilities.GetPlayers().FirstOrDefault(p=>Human(p)&&p.SteamID.ToString()==localOwner);
        var pawn=player?.PlayerPawn.Value;
        if (petStage==0||chickenBreed=="off"||pawn?.IsValid!=true||!player!.PawnIsAlive)
        {RemoveChicken();return;}
        if(chicken?.IsValid==true)
        {chicken.Leader.Raw=pawn.EntityHandle.Raw;chicken.Owner.Raw=player.EntityHandle.Raw;return;}
        var pet=Utilities.CreateEntityByName<CChicken>("chicken");
        if(pet==null||!pet.IsValid)return;
        pet.DispatchSpawn();
        pet.SetModel(petStage==1?"models/chicken/chick.vmdl":chickenBreed=="silkie"?"models/chicken/chicken_silkie.vmdl":chickenBreed=="polish"?"models/chicken/chicken_polish.vmdl":"models/chicken/chicken.vmdl");
        pet.Teleport(pawn.AbsOrigin,null,null);pet.TakesDamage=false;
        pet.Collision.SolidType=SolidType_t.SOLID_NONE;
        var item=pet.AttributeManager.Item;item.ItemDefinitionIndex=4681;item.ItemID=petInventoryId;item.ItemIDLow=(uint)petInventoryId;item.ItemIDHigh=(uint)(petInventoryId>>32);item.AccountID=(uint)player.SteamID;
        pet.Render=Color.White;
        pet.Leader.Raw=pawn.EntityHandle.Raw;pet.Owner.Raw=player.EntityHandle.Raw;pet.ActiveFollowStartTime=Server.CurrentTime;
        chicken=pet;
        if(petAccessory>=55000&&petAccessory<=55009)
        {
            var prop=Utilities.CreateEntityByName<CDynamicProp>("prop_dynamic");
            if(prop?.IsValid==true)
            {
                prop.SetModel("models/photobooth/silly_hats/"+HatModels[petAccessory-55000]+".vmdl");prop.DispatchSpawn();
                prop.TakesDamage=false;prop.Collision.SolidType=SolidType_t.SOLID_NONE;
                prop.AcceptInput("SetParent",pet,prop,"!activator");
                prop.AcceptInput("SetParentAttachment",pet,prop,petAccessory==55002||petAccessory==55003?"eyewear_attach":"head_attach");
                if(prop.CBodyComponent?.SceneNode!=null)prop.CBodyComponent.SceneNode.Scale=petStage==1?1f:petStage==2?.43f:.55f;
                hat=prop;
            }
        }
    }
    private bool Live()
    {
        if (ended) return false;
        var rules=Utilities.FindAllEntitiesByDesignerName<CCSGameRulesProxy>("cs_gamerules").FirstOrDefault()?.GameRules;
        return rules!=null && !rules.WarmupPeriod;
    }
    private static bool Human(CCSPlayerController? p) => p!=null && p.IsValid && !p.IsBot && !p.IsHLTV && p.SteamID!=0 && (p.TeamNum==2 || p.TeamNum==3);
    private static bool Enemy(CCSPlayerController? a,CCSPlayerController? v) => Human(a) && v!=null && v.IsValid && (v.TeamNum==2 || v.TeamNum==3) && a!.Index!=v.Index && a.TeamNum!=v.TeamNum;
    private void Add(CCSPlayerController p,string key)
    {
        string id=p.SteamID.ToString(System.Globalization.CultureInfo.InvariantCulture);
        if (!players.TryGetValue(id,out var counters)) players[id]=counters=new();
        counters.TryGetValue(key,out long value);
        counters[key]=Math.Min(1000000000L,value+1);sequence++;dirty=true;
    }
    private HookResult OnBlind(EventPlayerBlind e,GameEventInfo info)
    {
        var a=e.Attacker;var v=e.Userid;
        if (!Live() || !Enemy(a,v) || e.BlindDuration<1f || !float.IsFinite(e.BlindDuration)) return HookResult.Continue;
        var key=(e.Entityid,v!.Index);float now=Server.CurrentTime;
        if (flashes.TryGetValue(key,out float last) && now-last<2f) return HookResult.Continue;
        flashes[key]=now;
        if (flashes.Count>4096) foreach(var old in flashes.Where(x=>now-x.Value>4f).Select(x=>x.Key).ToArray()) flashes.Remove(old);
        Add(a!,"enemies_flashed");
        return HookResult.Continue;
    }
    private HookResult OnDeath(EventPlayerDeath e,GameEventInfo info)
    {
        if (!Live()) return HookResult.Continue;
        var a=e.Attacker;var v=e.Userid;
        if (v==null || !v.IsValid) return HookResult.Continue;
        if (deaths.TryGetValue(v.Index,out int tick) && tick==Server.TickCount) return HookResult.Continue;
        deaths[v.Index]=Server.TickCount;
        if(a!=null&&a.IsValid&&a.TeamNum!=v.TeamNum)
        {
            if(Human(a)&&v.IsBot)Chat(v,e.Headshot?.38f:.2f,e.Headshot?"nice shot":"well played",e.Headshot?"clean headshot":"you got me","good timing");
            else if(a.IsBot&&Human(v))Chat(a,.22f,"caught the timing","close one","good fight");
        }
        if (Enemy(a,v))
        {
            if (e.Thrusmoke) Add(a!,"smoke_kills");
            if (e.Attackerblind) Add(a!,"blind_kills");
            if (e.Noscope) Add(a!,"noscope_kills");
            if (e.Penetrated>0) Add(a!,"wallbang_kills");
            string w=e.Weapon.Replace("weapon_","").ToLowerInvariant();
            if (w=="hegrenade") Add(a!,"grenade_kills");
            else if (w=="inferno" || w=="molotov" || w=="incgrenade") Add(a!,"fire_kills");
            else if (w.StartsWith("knife") || w=="bayonet") Add(a!,"knife_kills");
            else if (w=="taser") Add(a!,"taser_kills");
            else if (new[]{"glock","hkp2000","usp_silencer","p250","fiveseven","tec9","cz75a","deagle","revolver","elite"}.Contains(w)) Add(a!,"pistol_kills");
            else if (new[]{"awp","ssg08","scar20","g3sg1"}.Contains(w)) Add(a!,"sniper_kills");
            else if (new[]{"mac10","mp9","mp7","mp5sd","ump45","p90","bizon"}.Contains(w)) Add(a!,"smg_kills");
            else if (new[]{"nova","xm1014","mag7","sawedoff"}.Contains(w)) Add(a!,"shotgun_kills");
            else if (w=="negev" || w=="m249") Add(a!,"heavy_kills");
            else if (new[]{"ak47","m4a1","m4a1_silencer","galilar","famas","aug","sg556"}.Contains(w)) Add(a!,"rifle_kills");
        }
        if (e.Assistedflash && Enemy(e.Assister,v) && (a==null || e.Assister!.Index!=a.Index)) Add(e.Assister!,"flash_assists");
        return HookResult.Continue;
    }
    private void Flush()
    {
        try
        {
            string meta=Path.Combine(directory,"cs2_gc_combat_session.json");
            if (!File.Exists(meta)) return;
            using var document=JsonDocument.Parse(File.ReadAllText(meta));var root=document.RootElement;
            if (root.GetProperty("pid").GetInt32()!=Environment.ProcessId) return;
            string current=root.GetProperty("nonce").GetString()??"";
            if (current.Length!=32) return;
            if (current!=nonce) { nonce=current;dirty=true; }
            string nextOwner=root.TryGetProperty("owner",out var owner)?owner.GetString()??"":"";
            if(nextOwner!=localOwner){RemoveChicken();localOwner=nextOwner;}
            string petPath=Path.Combine(directory,"cs2_gc_pets.json");
            if(File.Exists(petPath))
            {
                string text=File.ReadAllText(petPath);
                if(text!=petVersion)
                {
                    using var pets=JsonDocument.Parse(text);var petRoot=pets.RootElement;
                    string selected=petRoot.GetProperty("selected").GetString()??"0";
                    RemoveChicken();chickenBreed="off";petStage=0;
                    foreach(var entry in petRoot.GetProperty("pets").EnumerateArray())if(entry.GetProperty("id").GetString()==selected)
                    {petInventoryId=ulong.Parse(selected);petStage=entry.GetProperty("stage").GetInt32();petSeed=entry.GetProperty("seed").GetUInt32();petAccessory=entry.GetProperty("accessory").GetUInt32();chickenBreed=entry.GetProperty("breed").GetInt32() switch {4=>"silkie",5=>"polish",_=>"catalana"};}
                    petVersion=text;
                }
            }
            FollowChicken();
            if (!dirty) return;
            string path=Path.Combine(directory,"cs2_gc_combat_events.json");
            string data=JsonSerializer.Serialize(new{version=1,pid=Environment.ProcessId,nonce,session,sequence,players});
            File.WriteAllText(path+".tmp",data);File.Move(path+".tmp",path,true);dirty=false;
        }
        catch (Exception e) when(e is IOException || e is UnauthorizedAccessException || e is JsonException || e is KeyNotFoundException) {}
    }
}
