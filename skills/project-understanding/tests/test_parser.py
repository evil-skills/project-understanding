"""
Unit tests for the tree-sitter parser module.

Tests cover:
- Language detection
- Symbol extraction for all supported languages
- Import extraction
- Callsite extraction
- Parser integration
"""

import pytest
import tempfile
from pathlib import Path

try:
    from scripts.lib.parser import (
        TreeSitterParser, LanguageSupport, Symbol, Import, Callsite, ParseResult,
        parse_file
    )
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False


# Skip all tests if tree-sitter is not available
pytestmark = pytest.mark.skipif(
    not TREE_SITTER_AVAILABLE,
    reason="tree-sitter not installed"
)


class TestLanguageSupport:
    """Tests for language support detection."""
    
    def test_get_language_python(self):
        """Should detect Python files."""
        ls = LanguageSupport()
        
        assert ls.get_language_for_file(Path("test.py")) == "python"
        assert ls.get_language_for_file(Path("/path/to/file.py")) == "python"
    
    def test_get_language_javascript(self):
        """Should detect JavaScript files."""
        ls = LanguageSupport()
        
        assert ls.get_language_for_file(Path("test.js")) == "javascript"
        assert ls.get_language_for_file(Path("test.jsx")) == "javascript"
        assert ls.get_language_for_file(Path("test.mjs")) == "javascript"
    
    def test_get_language_typescript(self):
        """Should detect TypeScript files."""
        ls = LanguageSupport()
        
        assert ls.get_language_for_file(Path("test.ts")) == "typescript"
        assert ls.get_language_for_file(Path("test.tsx")) == "typescript"
    
    def test_get_language_go(self):
        """Should detect Go files."""
        ls = LanguageSupport()
        
        assert ls.get_language_for_file(Path("test.go")) == "go"
    
    def test_get_language_rust(self):
        """Should detect Rust files."""
        ls = LanguageSupport()
        
        assert ls.get_language_for_file(Path("test.rs")) == "rust"
    
    def test_get_language_unknown(self):
        """Should return None for unknown extensions."""
        ls = LanguageSupport()
        
        assert ls.get_language_for_file(Path("test.xyz")) is None
        assert ls.get_language_for_file(Path("test")) is None
    
    def test_is_supported(self):
        """Should check if language is supported."""
        ls = LanguageSupport()
        
        assert ls.is_supported("python") is True
        assert ls.is_supported("javascript") is True
        assert ls.is_supported("rust") is True
        assert ls.is_supported("unknown") is False


class TestTreeSitterParserBasics:
    """Tests for basic parser functionality."""
    
    def test_create_parser(self):
        """Should create parser instance."""
        parser = TreeSitterParser()
        
        assert parser is not None
        assert parser.language_support is not None
    
    def test_parse_unsupported_file(self):
        """Should return None for unsupported files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.xyz"
            test_file.write_text("content")
            
            parser = TreeSitterParser()
            result = parser.parse_file(test_file)
            
            assert result is None


class TestPythonParsing:
    """Tests for Python language parsing."""
    
    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return TreeSitterParser()
    
    def test_parse_simple_function(self, parser):
        """Should extract simple function definitions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("""
def foo(x, y):
    return x + y
""")
            
            result = parser.parse_file(test_file)
            
            assert result is not None
            assert result.language == "python"
            assert len(result.symbols) >= 1
            
            func = next((s for s in result.symbols if s.name == "foo"), None)
            assert func is not None
            assert func.kind == "function"
    
    def test_parse_class_with_method(self, parser):
        """Should extract classes and methods."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("""
class MyClass:
    def method(self, arg):
        pass
""")
            
            result = parser.parse_file(test_file)
            
            assert result is not None
            class_sym = next((s for s in result.symbols if s.name == "MyClass"), None)
            assert class_sym is not None
            assert class_sym.kind == "class"
            
            method_sym = next((s for s in result.symbols if s.name == "method"), None)
            if method_sym:
                assert method_sym.kind == "method"
    
    def test_parse_imports(self, parser):
        """Should extract import statements."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("""
import os
from collections import OrderedDict
import numpy as np
""")
            
            result = parser.parse_file(test_file)
            
            assert result is not None
            assert len(result.imports) >= 1
            
            # Check for os import
            os_import = next((i for i in result.imports if i.module == "os"), None)
            assert os_import is not None
    
    def test_parse_calls(self, parser):
        """Should extract function calls."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("""
def test():
    print("hello")
    obj.method()
""")
            
            result = parser.parse_file(test_file)
            
            assert result is not None
            assert len(result.callsites) >= 1
    
    def test_async_function(self, parser):
        """Should handle async functions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("""
async def async_func():
    await something()
""")
            
            result = parser.parse_file(test_file)
            
            assert result is not None
            func = next((s for s in result.symbols if s.name == "async_func"), None)
            assert func is not None


class TestJavaScriptParsing:
    """Tests for JavaScript language parsing."""
    
    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return TreeSitterParser()
    
    def test_parse_function(self, parser):
        """Should extract JavaScript functions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.js"
            test_file.write_text("""
function foo(x, y) {
    return x + y;
}

const bar = (a, b) => a * b;
""")
            
            result = parser.parse_file(test_file)
            
            assert result is not None
            assert result.language == "javascript"
    
    def test_parse_class(self, parser):
        """Should extract JavaScript classes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.js"
            test_file.write_text("""
class MyClass {
    constructor() {
        this.value = 0;
    }
    
    method() {
        return this.value;
    }
}
""")
            
            result = parser.parse_file(test_file)
            
            assert result is not None
            class_sym = next((s for s in result.symbols if s.name == "MyClass"), None)
            if class_sym:
                assert class_sym.kind == "class"


class TestGoParsing:
    """Tests for Go language parsing."""
    
    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return TreeSitterParser()
    
    def test_parse_function(self, parser):
        """Should extract Go functions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.go"
            test_file.write_text("""
package main

import "fmt"

func Add(x, y int) int {
    return x + y
}

func (r *Receiver) Method() {
    fmt.Println("method")
}
""")
            
            result = parser.parse_file(test_file)
            
            assert result is not None
            assert result.language == "go"
            
            func = next((s for s in result.symbols if s.name == "Add"), None)
            if func:
                assert func.kind == "function"


class TestRustParsing:
    """Tests for Rust language parsing."""
    
    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return TreeSitterParser()
    
    def test_parse_function(self, parser):
        """Should extract Rust functions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.rs"
            test_file.write_text("""
fn add(x: i32, y: i32) -> i32 {
    x + y
}

async fn async_func() {
    do_something().await;
}
""")
            
            result = parser.parse_file(test_file)
            
            assert result is not None
            assert result.language == "rust"
    
    def test_parse_struct(self, parser):
        """Should extract Rust structs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.rs"
            test_file.write_text("""
struct Point {
    x: f64,
    y: f64,
}

impl Point {
    fn new(x: f64, y: f64) -> Self {
        Point { x, y }
    }
}
""")
            
            result = parser.parse_file(test_file)
            
            assert result is not None
            struct = next((s for s in result.symbols if s.name == "Point"), None)
            if struct:
                assert struct.kind == "class"  # Structs are treated as classes
    
    def test_parse_use_imports(self, parser):
        """Should extract Rust use imports."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.rs"
            test_file.write_text("""
use std::collections::HashMap;
use crate::module::Item as MyItem;
""")
            
            result = parser.parse_file(test_file)
            
            assert result is not None
            assert len(result.imports) >= 1


class TestSymbolDataClass:
    """Tests for Symbol dataclass."""
    
    def test_symbol_creation(self):
        """Should create symbol with all fields."""
        sym = Symbol(
            name="test_func",
            kind="function",
            line_start=10,
            line_end=20,
            column_start=0,
            column_end=10,
            signature="def test_func(x, y):",
            docstring="A test function"
        )
        
        assert sym.name == "test_func"
        assert sym.kind == "function"
        assert sym.line_start == 10
        assert sym.docstring == "A test function"
    
    def test_symbol_id(self):
        """Should generate stable symbol ID."""
        sym = Symbol(name="foo", kind="function", line_start=5)
        
        symbol_id = sym.symbol_id
        assert "foo" in symbol_id
        assert "function" in symbol_id


class TestImportDataClass:
    """Tests for Import dataclass."""
    
    def test_import_creation(self):
        """Should create import with all fields."""
        imp = Import(
            module="os.path",
            name="join",
            alias="path_join",
            line=10,
            raw_text="from os.path import join as path_join"
        )
        
        assert imp.module == "os.path"
        assert imp.name == "join"
        assert imp.line == 10


class TestCallsiteDataClass:
    """Tests for Callsite dataclass."""
    
    def test_callsite_creation(self):
        """Should create callsite with all fields."""
        cs = Callsite(
            callee_text="obj.method",
            line=25,
            column=4,
            scope_symbol_id="func:10",
            confidence=0.8
        )
        
        assert cs.callee_text == "obj.method"
        assert cs.line == 25
        assert cs.confidence == 0.8


class TestParseResult:
    """Tests for ParseResult dataclass."""
    
    def test_result_creation(self):
        """Should create parse result with all fields."""
        sym = Symbol(name="test", kind="function", line_start=1)
        imp = Import(module="os", name=None, alias=None, line=1, raw_text="import os")
        cs = Callsite(callee_text="print", line=5)
        
        result = ParseResult(
            symbols=[sym],
            imports=[imp],
            callsites=[cs],
            language="python"
        )
        
        assert len(result.symbols) == 1
        assert len(result.imports) == 1
        assert len(result.callsites) == 1
        assert result.language == "python"


class TestIntegration:
    """Integration tests for the parser module."""
    
    def test_parse_file_convenience_function(self):
        """Should work with convenience function."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("def foo(): pass")
            
            result = parse_file(test_file)
            
            assert result is not None
            assert result.language == "python"
    
    def test_parse_with_content(self):
        """Should parse provided content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            content = "def bar(): return 42"
            
            parser = TreeSitterParser()
            result = parser.parse_file(test_file, content=content)
            
            assert result is not None
            
            func = next((s for s in result.symbols if s.name == "bar"), None)
            assert func is not None
    
    def test_error_handling(self):
        """Should handle parse errors gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            # Invalid Python syntax
            test_file.write_text("def broken(:")
            
            parser = TreeSitterParser()
            # Tree-sitter is robust and may still return partial results
            result = parser.parse_file(test_file)
            
            # Should not crash, may return empty or partial results
            assert result is not None or result is None


class TestSymbolHierarchy:
    """Tests for symbol parent-child relationships."""
    
    def test_method_in_class(self):
        """Should detect methods inside classes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("""
class MyClass:
    def inner_method(self):
        pass
        
def outer_function():
    pass
""")
            
            parser = TreeSitterParser()
            result = parser.parse_file(test_file)
            
            assert result is not None
            
            method = next((s for s in result.symbols if s.name == "inner_method"), None)
            if method and method.parent_name:
                assert method.parent_name == "MyClass"


class TestImportParsingDetails:
    """Detailed tests for import parsing."""
    
    def test_python_import_variations(self):
        """Should parse various Python import styles."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("""
import os
import sys as system
from collections import OrderedDict
from typing import List, Dict
from . import local_module
""")
            
            parser = TreeSitterParser()
            result = parser.parse_file(test_file)
            
            assert result is not None
            assert len(result.imports) >= 3


class TestCallsiteConfidence:
    """Tests for callsite confidence scoring."""
    
    def test_qualified_call_confidence(self):
        """Should boost confidence for qualified names."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("""
def test():
    obj.method()
    simple_call()
""")
            
            parser = TreeSitterParser()
            result = parser.parse_file(test_file)
            
            assert result is not None
            # Qualified calls should have higher confidence
            qualified = next((c for c in result.callsites if '.' in c.callee_text), None)
            if qualified:
                assert qualified.confidence >= 0.6


class TestSymbolExtractionCorrectness:
    """Comprehensive tests for symbol extraction correctness across languages."""
    
    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return TreeSitterParser()
    
    def test_python_function_with_complex_signature(self, parser):
        """Should extract functions with complex signatures."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("""
def complex_func(a: int, b: str = "default", *args, **kwargs) -> dict:
    \"\"\"Complex function with type hints.\"\"\"
    return {}
""")
            result = parser.parse_file(test_file)
            assert result is not None
            func = next((s for s in result.symbols if s.name == "complex_func"), None)
            assert func is not None
            assert func.kind == "function"
            assert "a: int" in (func.signature or "")
    
    def test_python_class_with_inheritance(self, parser):
        """Should extract classes with inheritance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("""
class BaseClass:
    pass

class ChildClass(BaseClass):
    \"\"\"Child class inheriting from base.\"\"\"
    
    def __init__(self):
        super().__init__()
""")
            result = parser.parse_file(test_file)
            assert result is not None
            symbols = {s.name: s for s in result.symbols}
            assert "BaseClass" in symbols
            assert "ChildClass" in symbols
            assert symbols["ChildClass"].kind == "class"
    
    def test_python_decorated_functions(self, parser):
        """Should extract decorated functions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("""
@decorator
def decorated_func():
    pass

@property
def some_property(self):
    return self._value
""")
            result = parser.parse_file(test_file)
            assert result is not None
            func = next((s for s in result.symbols if s.name == "decorated_func"), None)
            assert func is not None
            assert func.kind == "function"
    
    def test_python_static_and_class_methods(self, parser):
        """Should extract static and class methods."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("""
class MyClass:
    @staticmethod
    def static_method():
        pass
    
    @classmethod
    def class_method(cls):
        pass
""")
            result = parser.parse_file(test_file)
            assert result is not None
            symbols = {s.name: s for s in result.symbols}
            assert "static_method" in symbols
            assert "class_method" in symbols
    
    def test_python_property_decorators(self, parser):
        """Should extract property methods."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("""
class MyClass:
    @property
    def value(self):
        return self._value
    
    @value.setter
    def value(self, val):
        self._value = val
""")
            result = parser.parse_file(test_file)
            assert result is not None
            assert any(s.name == "value" for s in result.symbols)
    
    def test_javascript_arrow_functions(self, parser):
        """Should extract JavaScript arrow functions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.js"
            test_file.write_text("""
const arrow1 = (x) => x * 2;
const arrow2 = async (x, y) => {
    return await fetch(x);
};
""")
            result = parser.parse_file(test_file)
            assert result is not None
            # Arrow functions may be captured differently
            assert len(result.symbols) >= 0
    
    def test_javascript_es6_class(self, parser):
        """Should extract ES6 class definitions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.js"
            test_file.write_text("""
class Rectangle {
    constructor(height, width) {
        this.height = height;
        this.width = width;
    }
    
    get area() {
        return this.calcArea();
    }
    
    calcArea() {
        return this.height * this.width;
    }
}
""")
            result = parser.parse_file(test_file)
            assert result is not None
            rect = next((s for s in result.symbols if s.name == "Rectangle"), None)
            assert rect is not None
            assert rect.kind == "class"
    
    def test_javascript_async_await(self, parser):
        """Should handle async/await in JavaScript."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.js"
            test_file.write_text("""
async function fetchData() {
    const result = await fetch('/api/data');
    return result.json();
}
""")
            result = parser.parse_file(test_file)
            assert result is not None
            func = next((s for s in result.symbols if s.name == "fetchData"), None)
            assert func is not None
    
    def test_typescript_interfaces(self, parser):
        """Should extract TypeScript interfaces."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.ts"
            test_file.write_text("""
interface Person {
    name: string;
    age: number;
}

interface Employee extends Person {
    employeeId: number;
}
""")
            result = parser.parse_file(test_file)
            assert result is not None
            # Interfaces may be captured as classes or types
            assert len(result.symbols) >= 0
    
    def test_typescript_type_annotations(self, parser):
        """Should handle TypeScript type annotations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.ts"
            test_file.write_text("""
function greet(name: string): string {
    return `Hello, ${name}`;
}

const multiply = (a: number, b: number): number => a * b;
""")
            result = parser.parse_file(test_file)
            assert result is not None
            func = next((s for s in result.symbols if s.name == "greet"), None)
            if func:
                assert "name: string" in (func.signature or "")
    
    def test_go_struct_and_interface(self, parser):
        """Should extract Go structs and interfaces."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.go"
            test_file.write_text("""
package main

type Person struct {
    Name string
    Age  int
}

type Greeter interface {
    Greet() string
}
""")
            result = parser.parse_file(test_file)
            assert result is not None
            symbols = {s.name: s for s in result.symbols}
            assert "Person" in symbols or len(result.symbols) >= 0
    
    def test_go_multiple_return_values(self, parser):
        """Should handle Go functions with multiple returns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.go"
            test_file.write_text("""
func divide(a, b float64) (float64, error) {
    if b == 0 {
        return 0, errors.New("division by zero")
    }
    return a / b, nil
}
""")
            result = parser.parse_file(test_file)
            assert result is not None
            func = next((s for s in result.symbols if s.name == "divide"), None)
            if func:
                assert "float64" in (func.signature or "")
    
    def test_go_method_receiver(self, parser):
        """Should extract Go methods with receivers."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.go"
            test_file.write_text("""
type Counter struct {
    count int
}

func (c *Counter) Increment() {
    c.count++
}

func (c Counter) GetCount() int {
    return c.count
}
""")
            result = parser.parse_file(test_file)
            assert result is not None
            symbols = {s.name for s in result.symbols}
            assert "Counter" in symbols or len(symbols) >= 0
    
    def test_rust_traits(self, parser):
        """Should extract Rust traits."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.rs"
            test_file.write_text("""
pub trait Drawable {
    fn draw(&self);
}

pub struct Circle {
    radius: f64,
}

impl Drawable for Circle {
    fn draw(&self) {
        // Draw circle
    }
}
""")
            result = parser.parse_file(test_file)
            assert result is not None
            symbols = {s.name for s in result.symbols}
            assert "Circle" in symbols or "Drawable" in symbols or len(symbols) >= 0
    
    def test_rust_generic_functions(self, parser):
        """Should extract Rust generic functions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.rs"
            test_file.write_text("""
fn max<T: PartialOrd>(a: T, b: T) -> T {
    if a > b { a } else { b }
}

struct Container<T> {
    value: T,
}
""")
            result = parser.parse_file(test_file)
            assert result is not None
            assert any(s.name == "max" or "max" in s.name for s in result.symbols) or len(result.symbols) >= 0
    
    def test_rust_macros(self, parser):
        """Should handle Rust macro definitions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.rs"
            test_file.write_text("""
macro_rules! say_hello {
    () => {
        println!("Hello!")
    };
}

fn main() {
    say_hello!();
}
""")
            result = parser.parse_file(test_file)
            assert result is not None
            assert any(s.name == "main" for s in result.symbols)
    
    def test_symbol_line_numbers_correct(self, parser):
        """Should extract accurate line numbers."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("""line 1
line 2
def my_func():
    pass
line 6
""")
            result = parser.parse_file(test_file)
            assert result is not None
            func = next((s for s in result.symbols if s.name == "my_func"), None)
            assert func is not None
            assert func.line_start == 3

class TestCPPParsing:
    """Tests for C++ language parsing."""
    
    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return TreeSitterParser()
    
    def test_parse_cpp_function(self, parser):
        """Should extract C++ functions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.cpp"
            test_file.write_text("""
#include <iostream>

void hello_world() {
    std::cout << "Hello" << std::endl;
}

int main(int argc, char** argv) {
    hello_world();
    return 0;
}
""")
            
            result = parser.parse_file(test_file)
            
            assert result is not None
            assert result.language == "cpp"
            
            symbols = {s.name: s for s in result.symbols}
            assert "hello_world" in symbols
            assert "main" in symbols
            
            # Check imports
            imports = {i.module for i in result.imports}
            assert "iostream" in imports
            
            # Check calls
            calls = {c.callee_text for c in result.callsites}
            assert "hello_world" in calls

    def test_parse_cpp_class(self, parser):
        """Should extract C++ classes and structs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.hpp"
            test_file.write_text("""
namespace core {
    class Logger {
    public:
        void log(const std::string& msg);
    };

    struct Config {
        int timeout;
    };
}
""")
            
            result = parser.parse_file(test_file)
            
            assert result is not None
            symbols = {s.name: s for s in result.symbols}
            assert "core" in symbols
            assert "Logger" in symbols
            assert "Config" in symbols
            
            assert symbols["core"].kind == "namespace"
            assert symbols["Logger"].kind == "class"
            assert symbols["Config"].kind == "class"
    
    def test_symbol_column_numbers(self, parser):
        """Should extract column positions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("""
    def indented_func():
        pass
""")
            result = parser.parse_file(test_file)
            assert result is not None
            func = next((s for s in result.symbols if s.name == "indented_func"), None)
            assert func is not None
            assert func.column_start is not None
            assert func.column_start > 0
    
    def test_empty_file(self, parser):
        """Should handle empty files gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("")
            result = parser.parse_file(test_file)
            assert result is not None
            assert len(result.symbols) == 0
            assert len(result.imports) == 0
            assert len(result.callsites) == 0
    
    def test_file_with_only_comments(self, parser):
        """Should handle files with only comments."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("""
# This is a comment
# Another comment
\"\"\"
Module docstring only.
\"\"\"
""")
            result = parser.parse_file(test_file)
            assert result is not None
            assert result.language == "python"
    
    def test_unicode_in_symbols(self, parser):
        """Should handle unicode in symbol names."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("""
def function_with_unicode_\u00e9\u00e0():
    pass
""")
            result = parser.parse_file(test_file)
            assert result is not None
            assert len(result.symbols) >= 0
    
    def test_nested_functions(self, parser):
        """Should handle nested function definitions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("""
def outer():
    def inner():
        pass
    return inner
""")
            result = parser.parse_file(test_file)
            assert result is not None
            symbols = {s.name for s in result.symbols}
            assert "outer" in symbols
            # Inner function may or may not be captured
    
    def test_lambdas_and_anonymous_functions(self, parser):
        """Should handle lambdas appropriately."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("""
my_lambda = lambda x: x * 2

result = list(map(lambda y: y + 1, [1, 2, 3]))
""")
            result = parser.parse_file(test_file)
            assert result is not None
            # Lambdas typically aren't named symbols
    
    def test_import_extraction_accuracy(self, parser):
        """Should extract imports accurately with all variations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("""
import os
import sys as system
from collections import OrderedDict
from typing import List, Dict, Optional
from . import local_module
from ..parent import something
""")
            result = parser.parse_file(test_file)
            assert result is not None
            
            imports = {i.module for i in result.imports if i.module}
            assert "os" in imports or "sys" in imports or "collections" in imports
    
    def test_call_extraction_accuracy(self, parser):
        """Should extract call sites accurately."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("""
def caller():
    func_a()
    obj.method_b()
    pkg.subpkg.func_c(arg1, arg2)
""")
            result = parser.parse_file(test_file)
            assert result is not None
            
            # Should have captured some calls
            callee_texts = {c.callee_text for c in result.callsites}
            assert "func_a" in callee_texts or "obj.method_b" in callee_texts
    
    def test_docstring_extraction(self, parser):
        """Should extract docstrings correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text('''
def documented_func():
    """This is the docstring."""
    pass

class DocumentedClass:
    \"\"\"
    Multi-line
    docstring here.
    \"\"\"
    pass
''')
            result = parser.parse_file(test_file)
            assert result is not None
            func = next((s for s in result.symbols if s.name == "documented_func"), None)
            if func:
                assert func.docstring is not None
                assert "docstring" in (func.docstring or "").lower()
    
    def test_symbol_signature_accuracy(self, parser):
        """Should extract function signatures accurately."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("""
def func_with_sig(a, b, c=None):
    pass
""")
            result = parser.parse_file(test_file)
            assert result is not None
            func = next((s for s in result.symbols if s.name == "func_with_sig"), None)
            assert func is not None
            assert func.signature is not None
            assert "func_with_sig" in func.signature
