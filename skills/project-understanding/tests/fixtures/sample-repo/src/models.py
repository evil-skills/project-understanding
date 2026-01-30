"""
Data models for the application.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List


@dataclass
class User:
    """User model."""
    id: int
    username: str
    email: str
    created_at: datetime
    is_active: bool = True
    
    def deactivate(self) -> None:
        """Deactivate the user."""
        self.is_active = False
    
    def activate(self) -> None:
        """Activate the user."""
        self.is_active = True


@dataclass
class Product:
    """Product model."""
    id: int
    name: str
    price: float
    description: Optional[str] = None
    tags: List[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
    
    def add_tag(self, tag: str) -> None:
        """Add a tag to the product."""
        if tag not in self.tags:
            self.tags.append(tag)
    
    def remove_tag(self, tag: str) -> None:
        """Remove a tag from the product."""
        if tag in self.tags:
            self.tags.remove(tag)


@dataclass
class Order:
    """Order model."""
    id: int
    user_id: int
    products: List[Product]
    total: float
    status: str = "pending"
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
    
    def calculate_total(self) -> float:
        """Recalculate order total."""
        return sum(p.price for p in self.products)
    
    def confirm(self) -> None:
        """Confirm the order."""
        self.status = "confirmed"
    
    def ship(self) -> None:
        """Mark order as shipped."""
        self.status = "shipped"
    
    def cancel(self) -> None:
        """Cancel the order."""
        self.status = "cancelled"
