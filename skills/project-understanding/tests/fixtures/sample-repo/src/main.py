"""
Main application module for sample-repo.

This module provides the core functionality for the application,
including data processing and API handlers.
"""

import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime

from .utils import validate_data, format_output
from .models import User, Product


logger = logging.getLogger(__name__)


@dataclass
class AppConfig:
    """Application configuration."""
    debug: bool = False
    port: int = 8080
    host: str = "localhost"
    database_url: str = "sqlite:///app.db"


class Application:
    """
    Main application class.
    
    Handles request routing, middleware setup, and lifecycle management.
    """
    
    def __init__(self, config: AppConfig):
        """Initialize application with configuration."""
        self.config = config
        self.routes: Dict[str, callable] = {}
        self.middleware: List[callable] = []
        self._running = False
    
    def register_route(self, path: str, handler: callable) -> None:
        """Register a route handler."""
        self.routes[path] = handler
        logger.info(f"Registered route: {path}")
    
    def add_middleware(self, middleware: callable) -> None:
        """Add middleware to the application."""
        self.middleware.append(middleware)
    
    async def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle incoming request.
        
        Args:
            request: Request dictionary containing path, method, body, etc.
            
        Returns:
            Response dictionary
        """
        path = request.get("path", "/")
        
        if path not in self.routes:
            return {"status": 404, "body": "Not found"}
        
        handler = self.routes[path]
        
        # Apply middleware
        for mw in self.middleware:
            request = await mw(request)
        
        try:
            response = await handler(request)
            return validate_data(response)
        except Exception as e:
            logger.error(f"Error handling request: {e}")
            return {"status": 500, "body": str(e)}
    
    def start(self) -> None:
        """Start the application."""
        self._running = True
        logger.info(f"Starting server on {self.config.host}:{self.config.port}")
    
    def stop(self) -> None:
        """Stop the application."""
        self._running = False
        logger.info("Application stopped")


def create_app(config: Optional[AppConfig] = None) -> Application:
    """Factory function to create application instance."""
    if config is None:
        config = AppConfig()
    return Application(config)


class DataProcessor:
    """Process and transform data."""
    
    def __init__(self):
        self.processors: List[callable] = []
    
    def add_processor(self, processor: callable) -> None:
        """Add a data processor."""
        self.processors.append(processor)
    
    def process(self, data: List[Dict]) -> List[Dict]:
        """Process data through all processors."""
        result = data
        for processor in self.processors:
            result = [processor(item) for item in result]
        return result


def calculate_total(items: List[Product]) -> float:
    """Calculate total price of items."""
    return sum(item.price for item in items)


def format_timestamp(dt: datetime) -> str:
    """Format datetime to ISO string."""
    return dt.isoformat()
