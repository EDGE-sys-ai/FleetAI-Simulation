from typing import Dict, List, Optional
from models.warehouse import Warehouse
from models.product import Product, ProductStatus
from models.rack import Rack


class InventoryManager:
    def __init__(self):
        pass

    def receive_product(self, warehouse: Warehouse, product: Product) -> bool:
        if product.id in warehouse.products:
            return False

        warehouse.products[product.id] = product
        product.update_status(ProductStatus.RECEIVED, "INBOUND", "Product arrived at warehouse")
        return True

    def store_product(self, warehouse: Warehouse, product: Product, rack_id: str, shelf: int) -> bool:
        rack = warehouse.racks.get(rack_id)
        if not rack:
            return False

        shelf_obj = rack.get_shelf(shelf)
        if not shelf_obj or shelf_obj.is_full():
            return False

        shelf_obj.products.append(product.id)
        product.shelf = shelf
        product.update_status(ProductStatus.STORED, rack.get_location_string(shelf), f"Stored in {rack_id}")
        warehouse.inventory[product.id] = rack.get_location_string(shelf)
        return True

    def pick_product(self, warehouse: Warehouse, product_id: str) -> Optional[Product]:
        product = warehouse.products.get(product_id)
        if not product:
            return None

        if product.status != ProductStatus.STORED:
            return None

        location = warehouse.inventory.get(product_id)
        if location:
            rack_id = location.split('/')[0]
            rack = warehouse.racks.get(rack_id)
            if rack:
                rack.remove_product(product_id)

        product.update_status(ProductStatus.PICKED, "ROBOT", "Product picked for order")
        warehouse.inventory.pop(product_id, None)
        return product

    def ship_product(self, warehouse: Warehouse, product_id: str) -> Optional[Product]:
        product = warehouse.products.get(product_id)
        if not product:
            return None

        product.update_status(ProductStatus.SHIPPED, "OUTBOUND", "Product shipped")
        return product

    def transfer_out(self, warehouse: Warehouse, product_id: str) -> Optional[Product]:
        product = warehouse.products.get(product_id)
        if not product:
            return None

        location = warehouse.inventory.pop(product_id, None)
        if location:
            rack_id = location.split('/')[0]
            rack = warehouse.racks.get(rack_id)
            if rack:
                rack.remove_product(product_id)

        product.update_status(ProductStatus.IN_TRANSIT, "IN_TRANSIT", f"Transferred from {warehouse.id}")
        warehouse.products.pop(product_id, None)
        return product

    def receive_transfer(self, warehouse: Warehouse, product: Product) -> bool:
        if product.id in warehouse.products:
            return False

        product.warehouse_id = warehouse.id
        product.update_status(ProductStatus.RECEIVED, "INBOUND", f"Received from transfer")
        warehouse.products[product.id] = product
        return True

    def get_inventory_snapshot(self, warehouse: Warehouse) -> Dict:
        return {
            "warehouse_id": warehouse.id,
            "total_products": len(warehouse.products),
            "stored_products": len(warehouse.inventory),
            "inbound_queue": len(warehouse.inbound_queue),
            "outbound_queue": len(warehouse.outbound_queue),
            "rack_details": [
                {
                    "rack_id": rack.id,
                    "products": rack.get_products(),
                    "count": rack.get_product_count(),
                    "capacity": rack.capacity,
                    "utilization": round(rack.utilization(), 2),
                }
                for rack in warehouse.racks.values()
            ],
            "product_locations": dict(warehouse.inventory),
        }

    def find_product(self, warehouse: Warehouse, product_id: str) -> Optional[Product]:
        return warehouse.products.get(product_id)

    def get_products_by_status(self, warehouse: Warehouse, status: ProductStatus) -> List[Product]:
        return [p for p in warehouse.products.values() if p.status == status]

    def get_products_by_category(self, warehouse: Warehouse, category) -> List[Product]:
        return [p for p in warehouse.products.values() if p.category == category]