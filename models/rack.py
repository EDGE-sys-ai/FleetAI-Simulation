from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from models.product import Product, ProductCategory


@dataclass
class Shelf:
    id: int
    capacity: int
    products: List[str] = field(default_factory=list)

    def is_full(self) -> bool:
        return len(self.products) >= self.capacity

    def available_space(self) -> int:
        return self.capacity - len(self.products)

    def can_fit(self, product: Product) -> bool:
        return not self.is_full()


@dataclass
class Rack:
    id: str
    x: int
    y: int
    capacity: int
    shelves: int
    zone: str = "general"
    _shelves: Dict[int, Shelf] = field(default_factory=dict, init=False)

    def __post_init__(self):
        shelf_capacity = self.capacity // self.shelves
        for i in range(self.shelves):
            self._shelves[i] = Shelf(id=i, capacity=shelf_capacity)

    def get_shelf(self, shelf_num: int) -> Optional[Shelf]:
        return self._shelves.get(shelf_num)

    def add_product(self, product_id: str, preferred_shelf: int = None) -> Optional[int]:
        if preferred_shelf is not None and preferred_shelf in self._shelves:
            shelf = self._shelves[preferred_shelf]
            if shelf.can_fit(None):
                shelf.products.append(product_id)
                return preferred_shelf

        for shelf_num in range(self.shelves):
            shelf = self._shelves[shelf_num]
            if shelf.can_fit(None):
                shelf.products.append(product_id)
                return shelf_num
        return None

    def remove_product(self, product_id: str) -> bool:
        for shelf in self._shelves.values():
            if product_id in shelf.products:
                shelf.products.remove(product_id)
                return True
        return False

    def get_products(self) -> List[str]:
        products = []
        for shelf in self._shelves.values():
            products.extend(shelf.products)
        return products

    def get_product_count(self) -> int:
        return sum(len(s.products) for s in self._shelves.values())

    def is_full(self) -> bool:
        return all(s.is_full() for s in self._shelves.values())

    def utilization(self) -> float:
        total = sum(s.capacity for s in self._shelves.values())
        used = sum(len(s.products) for s in self._shelves.values())
        return used / total if total > 0 else 0.0

    def get_location_string(self, shelf_num: int) -> str:
        return f"{self.id}/SHELF-{shelf_num:02d}"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "x": self.x,
            "y": self.y,
            "capacity": self.capacity,
            "shelves": self.shelves,
            "zone": self.zone,
            "product_count": self.get_product_count(),
            "utilization": round(self.utilization(), 2),
            "shelf_details": {
                str(shelf_num): {
                    "products": shelf.products,
                    "capacity": shelf.capacity,
                    "utilization": round(len(shelf.products) / shelf.capacity, 2) if shelf.capacity > 0 else 0,
                }
                for shelf_num, shelf in self._shelves.items()
            },
        }