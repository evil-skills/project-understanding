"""
Architecture inference for detecting frameworks and application layers.

Provides detection of:
- Web frameworks (Flask, Django, FastAPI, Express, etc.)
- CLI frameworks (Click, Argparse, Typer, etc.)
- Application layers (routes, controllers, services, models)
"""

from typing import List, Dict, Any, Optional, Set, Tuple
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
import re


class FrameworkType(Enum):
    """Types of frameworks that can be detected."""
    WEB = "web"
    CLI = "cli"
    EVENT_DRIVEN = "event_driven"
    TESTING = "testing"
    UNKNOWN = "unknown"


class LayerType(Enum):
    """Application layer types."""
    ROUTES = "routes"
    CONTROLLERS = "controllers"
    SERVICES = "services"
    MODELS = "models"
    VIEWS = "views"
    MIDDLEWARE = "middleware"
    COMMANDS = "commands"
    HANDLERS = "handlers"
    UTILS = "utils"
    CONFIG = "config"


@dataclass
class Framework:
    """Detected framework information."""
    name: str
    type: FrameworkType
    confidence: float  # 0.0 to 1.0
    files: List[str] = field(default_factory=list)
    entry_points: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'type': self.type.value,
            'confidence': round(self.confidence, 2),
            'files': self.files,
            'entry_points': self.entry_points
        }


@dataclass
class Layer:
    """Application layer information."""
    type: LayerType
    files: List[str] = field(default_factory=list)
    symbols: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': self.type.value,
            'file_count': len(self.files),
            'files': self.files[:10],  # Limit for brevity
            'symbol_count': len(self.symbols)
        }


@dataclass
class ArchitecturePack:
    """Complete architecture analysis pack."""
    frameworks: List[Framework] = field(default_factory=list)
    layers: List[Layer] = field(default_factory=list)
    patterns: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'frameworks': [f.to_dict() for f in self.frameworks],
            'layers': [l.to_dict() for l in self.layers],
            'patterns': self.patterns,
            'recommendations': self.recommendations
        }
    
    def to_text(self) -> str:
        """Convert to formatted text."""
        lines = [
            "# Architecture Analysis",
            "",
            "## Detected Frameworks",
            ""
        ]
        
        if self.frameworks:
            for fw in self.frameworks:
                lines.append(f"- **{fw.name}** ({fw.type.value}) - confidence: {fw.confidence:.0%}")
                if fw.entry_points:
                    lines.append(f"  - Entry points: {', '.join(fw.entry_points[:3])}")
        else:
            lines.append("No frameworks detected.")
        
        lines.extend(["", "## Application Layers", ""])
        
        if self.layers:
            for layer in self.layers:
                lines.append(f"- **{layer.type.value}**: {len(layer.files)} files, {len(layer.symbols)} symbols")
        else:
            lines.append("No clear layer structure detected.")
        
        if self.patterns:
            lines.extend(["", "## Architectural Patterns", ""])
            for pattern in self.patterns:
                lines.append(f"- {pattern}")
        
        if self.recommendations:
            lines.extend(["", "## Recommendations", ""])
            for rec in self.recommendations:
                lines.append(f"- {rec}")
        
        return '\n'.join(lines)


class FrameworkDetector:
    """Detects frameworks used in the codebase."""
    
    # Framework signatures: (name, type, import_patterns, decorator_patterns)
    FRAMEWORK_SIGNATURES = [
        # Web frameworks
        ("Flask", FrameworkType.WEB, [r"from flask", r"import flask"], [r"@app\.route", r"@.*\.route"]),
        ("Django", FrameworkType.WEB, [r"from django", r"import django"], [r"@.*\.dispatch", r"class.*View"]),
        ("FastAPI", FrameworkType.WEB, [r"from fastapi", r"import fastapi"], [r"@app\.get", r"@.*\.(get|post|put|delete)"]),
        ("Express", FrameworkType.WEB, [r"require\(['\"]express['\"]\)"], [r"app\.(get|post|put|delete)"]),
        ("Spring Boot", FrameworkType.WEB, [r"import org\.springframework"], [r"@RestController", r"@RequestMapping"]),
        
        # CLI frameworks
        ("Click", FrameworkType.CLI, [r"import click", r"from click"], [r"@click\.command", r"@click\.group"]),
        ("Typer", FrameworkType.CLI, [r"import typer", r"from typer"], [r"@app\.command", r"typer\.Typer"]),
        ("Argparse", FrameworkType.CLI, [r"import argparse", r"from argparse"], [r"ArgumentParser"]),
        
        # Event-driven
        ("Celery", FrameworkType.EVENT_DRIVEN, [r"from celery", r"import celery"], [r"@app\.task", r"@.*\.task"]),
        ("RQ", FrameworkType.EVENT_DRIVEN, [r"from rq", r"import rq"], [r"@job"]),
        
        # Testing
        ("pytest", FrameworkType.TESTING, [r"import pytest", r"from pytest"], [r"@pytest\.fixture", r"def test_"]),
        ("unittest", FrameworkType.TESTING, [r"import unittest", r"from unittest"], [r"class.*TestCase"]),
    ]
    
    def detect_frameworks(self, files_content: Dict[str, str]) -> List[Framework]:
        """Detect frameworks from file contents."""
        frameworks = []
        
        for name, fw_type, import_patterns, decorator_patterns in self.FRAMEWORK_SIGNATURES:
            matched_files = []
            entry_points = []
            
            for file_path, content in files_content.items():
                # Check imports
                import_match = any(re.search(pattern, content) for pattern in import_patterns)
                
                # Check decorators/usage
                decorator_match = any(re.search(pattern, content) for pattern in decorator_patterns)
                
                if import_match or decorator_match:
                    matched_files.append(file_path)
                    
                    # Try to find entry points
                    if decorator_match:
                        for pattern in decorator_patterns:
                            for match in re.finditer(pattern, content):
                                # Extract some context
                                start = max(0, match.start() - 50)
                                end = min(len(content), match.end() + 50)
                                entry_points.append(content[start:end].strip()[:50])
            
            if matched_files:
                # Calculate confidence based on number of files and patterns
                confidence = min(1.0, (len(matched_files) * 0.2) + (0.3 if entry_points else 0))
                
                frameworks.append(Framework(
                    name=name,
                    type=fw_type,
                    confidence=confidence,
                    files=matched_files,
                    entry_points=list(set(entry_points))[:5]  # Deduplicate and limit
                ))
        
        # Sort by confidence
        frameworks.sort(key=lambda f: f.confidence, reverse=True)
        return frameworks


class LayerClassifier:
    """Classifies files into application layers."""
    
    # Layer detection patterns: (layer_type, path_patterns, content_patterns)
    LAYER_PATTERNS = [
        (LayerType.ROUTES, [r"[/\\]routes", r"[/\\]urls", r"[/\\]endpoints"], [r"@.*\.route", r"@.*\.(get|post|put|delete)"]),
        (LayerType.CONTROLLERS, [r"[/\\]controllers?", r"[/\\]handlers?"], [r"class.*Controller", r"def handle"]),
        (LayerType.SERVICES, [r"[/\\]services?", r"[/\\]business", r"[/\\]logic"], [r"class.*Service", r"def process"]),
        (LayerType.MODELS, [r"[/\\]models?", r"[/\\]entities?", r"[/\\]domain"], [r"class.*Model", r"BaseModel", r"@dataclass"]),
        (LayerType.VIEWS, [r"[/\\]views?", r"[/\\]templates?"], [r"def render", r"class.*View"]),
        (LayerType.MIDDLEWARE, [r"[/\\]middleware"], [r"class.*Middleware", r"def process_request"]),
        (LayerType.COMMANDS, [r"[/\\]commands?", r"[/\\]cli"], [r"@click\.command", r"@.*\.command"]),
        (LayerType.HANDLERS, [r"[/\\]handlers?", r"[/\\]consumers?"], [r"def handle", r"def consume"]),
        (LayerType.CONFIG, [r"[/\\]config", r"[/\\]settings"], [r"CONFIG", r"SETTINGS", r"class.*Config"]),
        (LayerType.UTILS, [r"[/\\]utils?", r"[/\\]helpers?"], [r"def helper", r"def util"]),
    ]
    
    def classify_layers(self, files_content: Dict[str, str]) -> List[Layer]:
        """Classify files into layers."""
        layers = {layer_type: Layer(type=layer_type) for layer_type in LayerType}
        
        for file_path, content in files_content.items():
            classified = False
            
            for layer_type, path_patterns, content_patterns in self.LAYER_PATTERNS:
                # Check path patterns
                path_match = any(re.search(pattern, file_path) for pattern in path_patterns)
                
                # Check content patterns
                content_match = any(re.search(pattern, content) for pattern in content_patterns)
                
                if path_match or content_match:
                    layers[layer_type].files.append(file_path)
                    classified = True
                    break
            
            # If not classified, try to infer from imports and structure
            if not classified:
                if self._looks_like_model(content):
                    layers[LayerType.MODELS].files.append(file_path)
                elif self._looks_like_service(content):
                    layers[LayerType.SERVICES].files.append(file_path)
        
        # Return only layers with files
        return [layer for layer in layers.values() if layer.files]
    
    def _looks_like_model(self, content: str) -> bool:
        """Heuristic to detect if content looks like a data model."""
        model_patterns = [
            r"@dataclass",
            r"BaseModel",
            r"class.*:\s*\n.*="  # Class with attribute assignments
        ]
        return any(re.search(p, content) for p in model_patterns)
    
    def _looks_like_service(self, content: str) -> bool:
        """Heuristic to detect if content looks like a service."""
        service_patterns = [
            r"class.*Service",
            r"def.*process",
            r"def.*handle"
        ]
        return any(re.search(p, content) for p in service_patterns)


class PatternDetector:
    """Detects architectural patterns in the codebase."""
    
    PATTERNS = [
        ("MVC Architecture", [LayerType.MODELS, LayerType.VIEWS, LayerType.CONTROLLERS]),
        ("Layered Architecture", [LayerType.CONTROLLERS, LayerType.SERVICES, LayerType.MODELS]),
        ("Repository Pattern", [r"class.*Repository", r"def.*find.*by"]),
        ("Dependency Injection", [r"@inject", r"def __init__.*"]),
        ("Factory Pattern", [r"class.*Factory", r"def create"]),
        ("Observer Pattern", [r"\.subscribe", r"\.emit", r"@.*\.listen"]),
    ]
    
    def detect_patterns(self, layers: List[Layer], files_content: Dict[str, str]) -> List[str]:
        """Detect architectural patterns."""
        detected = []
        
        # Check layer-based patterns
        layer_types = {layer.type for layer in layers}
        
        for pattern_name, required_layers in self.PATTERNS:
            if isinstance(required_layers[0], LayerType):
                # Layer-based pattern
                if all(layer in layer_types for layer in required_layers):
                    detected.append(pattern_name)
            else:
                # Content-based pattern
                pattern_found = False
                for content in files_content.values():
                    if all(re.search(p, content) for p in required_layers):
                        pattern_found = True
                        break
                if pattern_found:
                    detected.append(pattern_name)
        
        return detected


class ArchitectureAnalyzer:
    """Main analyzer for architecture inference."""
    
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.framework_detector = FrameworkDetector()
        self.layer_classifier = LayerClassifier()
        self.pattern_detector = PatternDetector()
    
    def analyze(self, files_content: Dict[str, str]) -> ArchitecturePack:
        """Perform full architecture analysis."""
        pack = ArchitecturePack()
        
        # Detect frameworks
        pack.frameworks = self.framework_detector.detect_frameworks(files_content)
        
        # Classify layers
        pack.layers = self.layer_classifier.classify_layers(files_content)
        
        # Detect patterns
        pack.patterns = self.pattern_detector.detect_patterns(pack.layers, files_content)
        
        # Generate recommendations
        pack.recommendations = self._generate_recommendations(pack)
        
        return pack
    
    def _generate_recommendations(self, pack: ArchitecturePack) -> List[str]:
        """Generate recommendations based on analysis."""
        recommendations = []
        
        # Framework recommendations
        web_frameworks = [f for f in pack.frameworks if f.type == FrameworkType.WEB]
        if len(web_frameworks) > 1:
            recommendations.append("Multiple web frameworks detected. Consider standardizing on one.")
        
        # Layer recommendations
        layer_types = {layer.type for layer in pack.layers}
        
        if LayerType.SERVICES not in layer_types and LayerType.CONTROLLERS in layer_types:
            recommendations.append("Consider adding a service layer to separate business logic from controllers.")
        
        if LayerType.MODELS not in layer_types:
            recommendations.append("No clear model layer detected. Consider organizing data structures into models.")
        
        # Pattern recommendations
        if "Repository Pattern" not in pack.patterns and LayerType.MODELS in layer_types:
            recommendations.append("Consider using the Repository pattern for data access abstraction.")
        
        return recommendations


def analyze_architecture(repo_root: Path, files_content: Optional[Dict[str, str]] = None) -> ArchitecturePack:
    """Convenience function to analyze repository architecture."""
    analyzer = ArchitectureAnalyzer(repo_root)
    
    if files_content is None:
        # Load files from repo
        files_content = {}
        for ext in ["*.py", "*.js", "*.ts", "*.go", "*.rs"]:
            for file_path in repo_root.rglob(ext):
                try:
                    rel_path = str(file_path.relative_to(repo_root))
                    files_content[rel_path] = file_path.read_text()
                except Exception:
                    pass
    
    return analyzer.analyze(files_content)
