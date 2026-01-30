;; Rust Tree-sitter queries for Project Understanding
;; Captures: functions, methods, structs, enums, traits, impls, imports, calls

;; Function definitions
(
  (function_item
    name: (identifier) @name
    parameters: (parameters) @signature
    return_type: (_)? @return_type) @function
)

;; Async functions
(
  (function_item
    "async"
    name: (identifier) @name
    parameters: (parameters) @signature) @async_function
)

;; Const functions
(
  (function_item
    "const"
    name: (identifier) @name
    parameters: (parameters) @signature) @const_function
)

;; Unsafe functions
(
  (function_item
    "unsafe"
    name: (identifier) @name
    parameters: (parameters) @signature) @unsafe_function
)

;; Struct definitions
(
  (struct_item
    name: (type_identifier) @name
    type_parameters: (type_parameters)? @type_params
    body: (field_declaration_list) @fields) @struct
)

;; Tuple struct definitions
(
  (struct_item
    name: (type_identifier) @name
    type_parameters: (type_parameters)? @type_params
    body: (ordered_field_declaration_list) @fields) @tuple_struct
)

;; Enum definitions
(
  (enum_item
    name: (type_identifier) @name
    type_parameters: (type_parameters)? @type_params
    body: (enum_variant_list) @variants) @enum
)

;; Trait definitions
(
  (trait_item
    name: (type_identifier) @name
    type_parameters: (type_parameters)? @type_params
    body: (declaration_list) @trait_items) @trait
)

;; Trait methods
(
  (function_signature_item
    name: (identifier) @name
    parameters: (parameters) @signature
    return_type: (_)? @return_type) @trait_method
)

;; Implementation blocks
(
  (impl_item
    type: (type_identifier) @name
    type_parameters: (type_parameters)? @type_params
    trait: (trait_bounds)? @trait) @impl
)

;; Trait implementations
(
  (impl_item
    trait: (type_identifier) @trait_name
    "for"
    type: (type_identifier) @type_name) @trait_impl
)

;; Method definitions (in impl blocks)
(
  (function_item
    name: (identifier) @name
    parameters: (parameters) @signature
    return_type: (_)? @return_type) @method
  (#parent-type? @method impl_item)
)

;; Use declarations (imports)
(use_declaration) @import

;; Simple use statements
(
  (use_declaration
    (scoped_identifier) @import_path)
)

;; Use with alias
(
  (use_declaration
    (use_as_clause
      path: (_) @import_path
      alias: (identifier) @import_alias))
)

;; Use wildcards
(
  (use_declaration
    (use_wildcard) @wildcard)
)

;; Use lists
(
  (use_declaration
    (use_list) @import_list)
)

;; Call expressions
(call_expression
  function: (_) @call) @call_expr

;; Method calls (obj.method())
(call_expression
  function: (field_expression
    value: (_) @object
    field: (field_identifier) @method_name) @call)

;; Static method calls (Type::method())
(call_expression
  function: (scoped_identifier
    path: (_) @type_path
    name: (identifier) @method_name) @call)

;; Macro invocations
(macro_invocation
  macro: (identifier) @macro_name) @macro

;; Macro rules definitions
(
  (macro_definition
    name: (identifier) @name) @macro_def
)

;; Const declarations
(
  (const_item
    name: (identifier) @name
    type: (_)? @const_type) @const
)

;; Static declarations
(
  (static_item
    name: (identifier) @name
    type: (_)? @static_type) @static
)

;; Type aliases
(
  (type_item
    name: (type_identifier) @name
    type_parameters: (type_parameters)? @type_params
    type: (_) @aliased_type) @type_alias
)

;; Mod declarations
(
  (mod_item
    name: (identifier) @name) @module
)

;; Extern crate declarations
(
  (extern_crate_declaration
    name: (identifier) @crate_name
    alias: (identifier)? @crate_alias) @extern_crate
)

;; Generic functions
(
  (function_item
    name: (identifier) @name
    type_parameters: (type_parameters) @type_params
    parameters: (parameters) @signature) @generic_function
)

;; Closures
(
  (closure_expression
    parameters: (closure_parameters) @signature) @closure
)

;; Lifetime bounds in function signatures
(
  (function_item
    name: (identifier) @name
    type_parameters: (type_parameters
      (lifetime) @lifetime_constraint)+) @function_with_lifetime
)

;; Public items
(
  (function_item
    "pub" @visibility
    name: (identifier) @name) @public_function
)

(
  (struct_item
    "pub" @visibility
    name: (type_identifier) @name) @public_struct
)

(
  (enum_item
    "pub" @visibility
    name: (type_identifier) @name) @public_enum
)
