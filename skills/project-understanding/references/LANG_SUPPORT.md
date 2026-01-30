# Language Support

This document describes the programming languages supported by the Project Understanding Skill and their parsing capabilities.

## Supported Languages

| Language | Extensions | Parser Status | Symbol Extraction | Import Resolution | Call Graph |
|----------|-----------|---------------|-------------------|-------------------|------------|
| Python | .py | Full | Full | Full | Full |
| JavaScript | .js, .jsx, .mjs | Full | Full | Partial | Full |
| TypeScript | .ts, .tsx | Full | Full | Partial | Full |
| Go | .go | Full | Full | Full | Full |
| Rust | .rs | Full | Full | Full | Full |

## Parsing Technology

All languages are parsed using **Tree-sitter**, a fast, incremental parser generator. We use the `tree-sitter-languages` Python package which provides prebuilt grammars for supported languages.

### Dependencies

```bash
# Required
pip install tree-sitter tree-sitter-languages

# System dependencies
# - None required (pure Python bindings)
```

## Python

### Supported Features

- **Function Definitions**: Regular functions, async functions, decorated functions
- **Method Definitions**: Instance methods, static methods, class methods
- **Class Definitions**: Classes with inheritance
- **Lambda Functions**: Anonymous functions
- **Imports**: `import X`, `from X import Y`, `import X as Y`
- **Calls**: Direct calls, method calls (obj.method()), chained calls
- **Docstrings**: Module, class, and function docstrings

### Limitations

- Type hints in signatures are captured as text (not parsed)
- Dynamic imports (`__import__`, `importlib`) not tracked
- Relative imports resolved only with package context

### Example Queries

```python
# Function
def foo(x: int, y: str) -> bool:
    pass

# Method
class MyClass:
    def method(self, arg):
        pass

# Import
from module import name as alias
```

## JavaScript

### Supported Features

- **Functions**: Function declarations, expressions, arrow functions
- **Methods**: Class methods, getters, setters
- **Classes**: ES6 classes with inheritance
- **Imports**: ES6 import statements (named, default, namespace)
- **Calls**: Function calls, method calls, constructor calls
- **Async/Gens**: Async functions, generator functions

### Limitations

- CommonJS `require()` not tracked as imports
- Dynamic imports (`import()`) not tracked
- JSX components treated as call expressions

### Example Queries

```javascript
// Function
function foo(x, y) { return x + y; }

// Arrow function
const bar = (a, b) => a * b;

// Method
class MyClass {
    method(arg) { }
    get value() { }
}

// Import
import { name } from 'module';
```

## TypeScript

### Supported Features

- **All JavaScript features** plus:
- **Type Annotations**: Parameter types, return types
- **Interfaces**: Interface declarations
- **Type Aliases**: Type definitions
- **Generics**: Generic functions and types
- **Enums**: Enum declarations
- **Abstract Classes**: Abstract methods and classes
- **Decorators**: Method/class decorators

### Limitations

- Type-only imports (`import type`) distinguished but not fully resolved
- Declaration merging not fully tracked
- Namespace/module declarations parsed as basic symbols

### Example Queries

```typescript
// Function with types
function foo<T>(x: T): T { return x; }

// Interface
interface Person {
    name: string;
    age: number;
}

// Generic class
class Container<T> {
    value: T;
}

// Import with types
import type { SomeType } from 'module';
```

## Go

### Supported Features

- **Functions**: Regular functions with multiple return values
- **Methods**: Receiver methods (pointer and value)
- **Types**: Type definitions, struct types, interface types
- **Imports**: Single and grouped imports
- **Calls**: Direct calls, method calls
- **Generics**: Generic functions and types (Go 1.18+)

### Limitations

- Interface satisfaction not computed
- Build tags not considered
- Cgo imports tracked but not resolved

### Example Queries

```go
// Function
func Add(x, y int) int { return x + y }

// Method
func (r *Receiver) Method() { }

// Interface
type Reader interface {
    Read([]byte) (int, error)
}

// Import
import "fmt"
import (
    "os"
    "strings"
)
```

## Rust

### Supported Features

- **Functions**: Regular, async, const, unsafe functions
- **Methods**: Impl block methods, trait methods
- **Structs**: Named structs, tuple structs
- **Enums**: Enum definitions with variants
- **Traits**: Trait definitions with methods
- **Impls**: Implementation blocks, trait implementations
- **Imports**: Use declarations, extern crates
- **Macros**: Macro definitions, macro invocations
- **Generics**: Generic types and lifetime parameters

### Limitations

- Macro expansion not performed
- Complex trait bounds simplified
- Module path resolution requires full crate context

### Example Queries

```rust
// Function
fn foo<T: Display>(x: T) { }

// Method
impl MyStruct {
    fn method(&self) { }
}

// Trait
trait Drawable {
    fn draw(&self);
}

// Use import
use std::collections::HashMap;
use crate::module::Item as Alias;
```

## Symbol Types

The following symbol kinds are extracted across all languages:

| Kind | Description |
|------|-------------|
| `function` | Standalone function |
| `method` | Method (member of class/struct) |
| `class` | Class, struct, or interface |
| `variable` | Module-level variable/constant |
| `import` | Import/use statement |
| `call` | Function/method call site |

## Call Graph Accuracy

Call graph construction uses confidence scoring:

- **0.8-1.0**: Qualified names (obj.method, pkg.Function)
- **0.6-0.8**: Simple identifiers with import hints
- **0.4-0.6**: Simple identifiers without context
- **0.0-0.4**: Complex expressions (callbacks, dynamic dispatch)

## Adding New Languages

To add support for a new language:

1. Create `scripts/lib/queries/<lang>.scm` with tree-sitter queries
2. Add language to `LanguageSupport.SUPPORTED_LANGUAGES`
3. Add file extension mappings in config
4. Update this documentation

### Query File Structure

```scheme
;; functions.scm
(function_declaration
  name: (identifier) @name
  parameters: (parameters) @signature) @function

;; imports.scm
(import_statement) @import

;; calls.scm
(call_expression
  function: (_) @call) @call_expr
```

## Performance Considerations

- **Parsing Speed**: ~1000-5000 lines/second depending on language
- **Memory**: AST retained only during file processing
- **Incremental**: Only changed files re-parsed
- **Batch Size**: Recommended 100-1000 files per transaction

## Error Handling

Parser failures are handled gracefully:

- Syntax errors in a file don't crash the indexer
- Partial parse results are used when available
- Errors are logged and stored in the database
- Fallback to simple text extraction for unsupported constructs

## Future Improvements

- [ ] Add C/C++ support (via clangd or tree-sitter-cpp)
- [ ] Add Java support
- [ ] Add C# support
- [ ] Add Ruby support
- [ ] Add PHP support
- [ ] Cross-file import resolution
- [ ] Type inference for call targets
- [ ] Macro expansion for Rust
- [ ] Template instantiation tracking for C++
