#pragma once

#include <cstdint>
#include <optional>
#include <span>
#include <string>
#include <vector>

namespace cs2_gc
{
// Field layouts below come from the descriptors embedded in the target client.dll
// (gcsdk_gcmessages.proto). Only the fields the handshake needs are modelled.

struct SoOwner // CMsgSOIDOwner
{
    std::uint32_t type{};
    std::uint64_t id{};
};

struct SoCacheVersion // CMsgSOCacheHaveVersion
{
    SoOwner owner;
    std::uint64_t version{};
};

struct ClientHello // CMsgClientHello
{
    std::optional<std::uint32_t> version;
    std::vector<SoCacheVersion> haveVersions;
    std::optional<std::uint32_t> clientSessionNeed;
    std::optional<std::uint32_t> clientLauncher;
    std::optional<std::uint32_t> steamLauncher;
};

struct SoObjectType // CMsgSOCacheSubscribed.SubscribedType
{
    std::int32_t typeId{};
    std::vector<std::vector<std::uint8_t>> objects; // serialized objects, opaque here
};

struct SoCacheSubscribed // CMsgSOCacheSubscribed
{
    SoOwner owner;
    std::uint64_t version{};
    std::vector<SoObjectType> types;
};

struct ClientWelcome // CMsgClientWelcome (subset)
{
    std::uint32_t version{};
    std::vector<SoCacheSubscribed> outOfDateCaches;
};

struct SoSingleObject // CMsgSOSingleObject: Create / Update / Destroy
{
    std::int32_t typeId{};
    std::vector<std::uint8_t> data;
    std::uint64_t version{};
    SoOwner owner;
};

struct SoMultipleObjects // CMsgSOMultipleObjects: UpdateMultiple
{
    struct Object
    {
        std::int32_t typeId{};
        std::vector<std::uint8_t> data;
    };
    std::vector<Object> objects;
    std::uint64_t version{};
    SoOwner owner;
};

struct EquipSlotChange // CMsgAdjustEquipSlot
{
    std::uint32_t classId{};
    std::uint32_t slotId{};
    std::uint64_t itemId{}; // zero clears the slot
};

struct AdjustEquipSlots // CMsgAdjustEquipSlots: the body of k_EMsgGCAdjustEquipSlotsManual
{
    std::vector<EquipSlotChange> slots;
    std::uint32_t changeNum{};
};

struct RedeemRequest // CMsgGCCstrike15_v2_ClientRedeemMissionReward (an Armory purchase)
{
    std::uint32_t campaignId{};
    std::uint32_t redeemId{};        // CRC32 of the goods' item name
    std::uint32_t redeemableBalance{}; // the balance the client believes it has
    std::uint32_t expectedCost{};
};

struct ApplyStickerRequest // CMsgApplySticker: the body of k_EMsgGCApplySticker
{
    std::uint64_t stickerItemId{};
    std::uint64_t targetItemId{};
    std::uint32_t slot{};
    float wear{};
    float rotation{};
    float scale{};
    float offsetX{};
    float offsetY{};
    float offsetZ{};
};

struct StorePurchaseRequest // CMsgGCStorePurchaseInit: the body of k_EMsgGCStorePurchaseInit
{
    struct Line // CGCStorePurchaseInit_LineItem
    {
        std::uint32_t defIndex{};
        std::uint32_t quantity{};
    };
    std::uint32_t currency{};
    std::vector<Line> lines;
};

struct OpenCrateRequest // CMsgOpenCrate: the body of k_EMsgGCOpenCrate
{
    std::uint64_t keyItemId{};   // tool_item_id; zero for containers that need no key
    std::uint64_t crateItemId{}; // subject_item_id
};

struct NameItemRequest // k_EMsgGCNameItem, fields as seen in a capture: 1 name tag item (0 here), 2 item, 4 name
{
    std::uint64_t tagItemId{};
    std::uint64_t itemId{};
    std::string name;
};

// Decoders reject malformed input outright; unknown fields are skipped.
std::optional<ClientHello> DecodeClientHello(std::span<const std::uint8_t> body);
std::optional<SoCacheSubscribed> DecodeSoCacheSubscribed(std::span<const std::uint8_t> body);
std::optional<ClientWelcome> DecodeClientWelcome(std::span<const std::uint8_t> body);
std::optional<SoSingleObject> DecodeSoSingleObject(std::span<const std::uint8_t> body);
std::optional<SoMultipleObjects> DecodeSoMultipleObjects(std::span<const std::uint8_t> body);

std::optional<ApplyStickerRequest> DecodeApplyStickerRequest(std::span<const std::uint8_t> body);
std::optional<StorePurchaseRequest> DecodeStorePurchaseRequest(std::span<const std::uint8_t> body);
std::optional<std::uint64_t> DecodeTxnId(std::span<const std::uint8_t> body); // Finalize / Cancel: field 1
std::optional<std::uint64_t> DecodeUseItemRequest(std::span<const std::uint8_t> body); // CMsgUseItem.item_id
std::optional<OpenCrateRequest> DecodeOpenCrateRequest(std::span<const std::uint8_t> body);
std::optional<NameItemRequest> DecodeNameItemRequest(std::span<const std::uint8_t> body);
std::optional<RedeemRequest> DecodeRedeemRequest(std::span<const std::uint8_t> body);
std::vector<std::uint8_t> EncodeSoSingleObject(const SoSingleObject &object);
std::optional<AdjustEquipSlots> DecodeAdjustEquipSlots(std::span<const std::uint8_t> body);
std::vector<std::uint8_t> EncodeSoMultipleObjects(const SoMultipleObjects &objects);
std::vector<std::uint8_t> EncodeSoCacheSubscribed(const SoCacheSubscribed &cache);
std::vector<std::uint8_t> EncodeClientWelcome(const ClientWelcome &welcome);
std::vector<std::uint8_t> EncodeClientHello(const ClientHello &hello);
}
