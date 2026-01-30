"""
Test cases for main module.
"""

import pytest
from src.main import Application, AppConfig, create_app, DataProcessor, calculate_total
from src.models import Product, User


class TestApplication:
    """Test Application class."""
    
    def test_create_app(self):
        """Test app factory."""
        app = create_app()
        assert app is not None
        assert app.config.debug is False
    
    def test_register_route(self):
        """Test route registration."""
        app = create_app()
        
        def handler(request):
            return {"status": 200}
        
        app.register_route("/test", handler)
        assert "/test" in app.routes
    
    def test_add_middleware(self):
        """Test middleware addition."""
        app = create_app()
        
        def middleware(request):
            return request
        
        app.add_middleware(middleware)
        assert len(app.middleware) == 1


class TestDataProcessor:
    """Test DataProcessor class."""
    
    def test_process_empty(self):
        """Test processing empty list."""
        processor = DataProcessor()
        result = processor.process([])
        assert result == []
    
    def test_add_processor(self):
        """Test adding processor."""
        processor = DataProcessor()
        
        def double(x):
            return {**x, "value": x["value"] * 2}
        
        processor.add_processor(double)
        assert len(processor.processors) == 1


class TestProduct:
    """Test Product model."""
    
    def test_product_creation(self):
        """Test product creation."""
        product = Product(
            id=1,
            name="Test Product",
            price=19.99
        )
        assert product.name == "Test Product"
        assert product.price == 19.99
    
    def test_add_tag(self):
        """Test adding tag to product."""
        product = Product(id=1, name="Test", price=10.0)
        product.add_tag("electronics")
        assert "electronics" in product.tags


class TestCalculateTotal:
    """Test calculate_total function."""
    
    def test_empty_list(self):
        """Test with empty list."""
        result = calculate_total([])
        assert result == 0.0
    
    def test_single_item(self):
        """Test with single item."""
        products = [Product(id=1, name="Test", price=10.0)]
        result = calculate_total(products)
        assert result == 10.0
    
    def test_multiple_items(self):
        """Test with multiple items."""
        products = [
            Product(id=1, name="A", price=10.0),
            Product(id=2, name="B", price=20.0),
            Product(id=3, name="C", price=30.0)
        ]
        result = calculate_total(products)
        assert result == 60.0
