import random
from typing import List, Dict, Optional
from models.product import Product, ProductCategory
from models.order import Order
from models.shipment import Shipment
from models.warehouse import Warehouse
from config import SIMULATION_CONFIG, PRODUCT_CATEGORIES


class SimulationGenerator:
    def __init__(self, warehouses: Dict[str, Warehouse]):
        self.warehouses = warehouses
        self.product_counter = 0
        self.order_counter = 0
        self.transfer_counter = 0

    def generate_initial_products(self, count: Optional[int] = None) -> List[Product]:
        count = count or SIMULATION_CONFIG.initial_products
        products = []
        warehouse_ids = list(self.warehouses.keys())

        for _ in range(count):
            warehouse_id = random.choice(warehouse_ids)
            category = random.choice(list(ProductCategory))
            product = Product.generate(category, warehouse_id)
            products.append(product)
            self.product_counter += 1

        return products

    def generate_product_arrival(self) -> Optional[Product]:
        if len(self._get_all_products()) >= SIMULATION_CONFIG.max_products:
            return None

        warehouse_id = random.choice(list(self.warehouses.keys()))
        category = random.choice(list(ProductCategory))
        product = Product.generate(category, warehouse_id)
        self.product_counter += 1
        return product

    def generate_customer_order(self) -> Optional[Order]:
        available_products = self._get_stored_products()
        if not available_products:
            return None

        warehouse_id = random.choice(list(self.warehouses.keys()))
        warehouse_products = [p for p in available_products if p.warehouse_id == warehouse_id]
        if not warehouse_products:
            return None

        num_items = random.randint(1, min(3, len(warehouse_products)))
        selected = random.sample(warehouse_products, num_items)
        product_ids = [p.id for p in selected]

        order = Order.create(warehouse_id, product_ids)
        self.order_counter += 1
        return order

    def generate_inter_warehouse_transfer(self) -> Optional[Shipment]:
        warehouse_ids = list(self.warehouses.keys())
        if len(warehouse_ids) < 2:
            return None

        origin_id = random.choice(warehouse_ids)
        dest_candidates = [w for w in warehouse_ids if w != origin_id]
        if not dest_candidates:
            return None
        dest_id = random.choice(dest_candidates)

        origin_products = [
            p for p in self._get_stored_products()
            if p.warehouse_id == origin_id and p.status.value == "STORED"
        ]
        if not origin_products:
            return None

        num_products = random.randint(1, min(3, len(origin_products)))
        selected = random.sample(origin_products, num_products)
        product_ids = [p.id for p in selected]

        shipment = Shipment.create(product_ids, origin_id, dest_id)
        self.transfer_counter += 1
        return shipment

    def _get_all_products(self) -> List[Product]:
        products: List[Product] = []
        for wh in self.warehouses.values():
            products.extend(wh.products.values())
        return products

    def _get_stored_products(self) -> List[Product]:
        products = []
        for wh in self.warehouses.values():
            for p in wh.products.values():
                if p.status.value in ("STORED", "ALLOCATED", "IN_STORAGE_TRANSIT"):
                    products.append(p)
        return products

    def get_stats(self) -> dict:
        return {
            "products_generated": self.product_counter,
            "orders_generated": self.order_counter,
            "transfers_generated": self.transfer_counter,
        }