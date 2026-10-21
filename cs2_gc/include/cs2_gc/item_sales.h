#pragma once
#include "cs2_gc/inventory.h"
#include "cs2_gc/schema.h"
namespace cs2_gc {
// OfflineCS buyback rules, applied only to owned, loose, ordinary items.
std::uint32_t ItemSaleValue(const Schema &schema, const GameplayConfig &config, const InventoryItem &item);
}
