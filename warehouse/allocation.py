from typing import Optional, List
from models.warehouse import Warehouse
from models.product import Product, ProductCategory
from models.rack import Rack
from config import CATEGORY_RACK_PREFERENCE


class RackAllocator:
    def __init__(self):
        self.category_preferences = CATEGORY_RACK_PREFERENCE

    def find_best_rack(self, warehouse: Warehouse, product: Product) -> Optional[Rack]:
        preferred_zones = self.category_preferences.get(product.category.value, ["middle"])
        candidates = []

        for rack in warehouse.racks.values():
            if not rack.is_full():
                priority = self._calculate_priority(rack, preferred_zones, product)
                candidates.append((priority, rack.utilization(), rack))

        if not candidates:
            return None

        candidates.sort(key=lambda x: (x[0], x[1]))
        return candidates[0][2]

    def _calculate_priority(self, rack: Rack, preferred_zones: List[str], product: Product) -> int:
        if rack.zone in preferred_zones:
            zone_index = preferred_zones.index(rack.zone)
            return zone_index
        return len(preferred_zones)

    def allocate(self, warehouse: Warehouse, product: Product) -> Optional[str]:
        rack = self.find_best_rack(warehouse, product)
        if rack:
            shelf = rack.add_product(product.id)
            if shelf is not None:
                product.shelf = shelf
                location = rack.get_location_string(shelf)
                warehouse.inventory[product.id] = location
                return rack.id
        return None

    def deallocate(self, warehouse: Warehouse, product: Product) -> bool:
        location = warehouse.inventory.pop(product.id, None)
        if not location:
            return False

        rack_id = location.split('/')[0]
        rack = warehouse.racks.get(rack_id)
        if rack:
            return rack.remove_product(product.id)
        return False

    def get_rack_utilization(self, warehouse: Warehouse) -> List[dict]:
        return [
            {
                "rack_id": rack.id,
                "zone": rack.zone,
                "utilization": rack.utilization(),
                "product_count": rack.get_product_count(),
                "capacity": rack.capacity,
            }
            for rack in warehouse.racks.values()
        ]

    def find_rack_for_category(self, warehouse: Warehouse, category: ProductCategory) -> List[Rack]:
        preferred = self.category_preferences.get(category.value, ["middle"])
        return [r for r in warehouse.racks.values() if r.zone in preferred and not r.is_full()]