;; Go Tree-sitter queries for Project Understanding
;; Captures: functions, methods, types, imports, calls

;; Function declarations
(
  (function_declaration
    name: (identifier) @name
    parameters: (parameter_list) @signature
    result: (_)? @return_type) @function
)

;; Method declarations (receiver methods)
(
  (method_declaration
    receiver: (parameter_list) @receiver
    name: (field_identifier) @name
    parameters: (parameter_list) @signature
    result: (_)? @return_type) @method
)

;; Type declarations
(
  (type_declaration
    (type_spec
      name: (type_identifier) @name
      type: (_) @type_def)) @type
)

;; Struct types
(
  (type_declaration
    (type_spec
      name: (type_identifier) @name
      type: (struct_type
        (field_declaration_list) @fields))) @struct
)

;; Interface types
(
  (type_declaration
    (type_spec
      name: (type_identifier) @name
      type: (interface_type
        (method_spec)* @methods))) @interface
)

;; Package declaration
(
  (package_clause
    (package_identifier) @package_name) @package
)

;; Import declarations
(import_declaration) @import

;; Single imports
(
  (import_spec
    name: (package_identifier)? @import_alias
    path: (interpreted_string_literal) @import_path) @import_spec
)

;; Import groups
(
  (import_declaration
    (import_spec_list
      (import_spec)+ @import_specs))
)

;; Call expressions
(call_expression
  function: (_) @call) @call_expr

;; Method calls (obj.Method())
(call_expression
  function: (selector_expression
    operand: (_) @object
    field: (field_identifier) @method_name) @call)

;; Function literals (anonymous functions)
(
  (func_literal
    parameters: (parameter_list) @signature
    result: (_)? @return_type) @anonymous_function
)

;; Type parameters (Go 1.18+)
(
  (function_declaration
    name: (identifier) @name
    type_parameters: (type_parameter_list) @type_params
    parameters: (parameter_list) @signature) @generic_function
)

;; Generic type declarations
(
  (type_declaration
    (type_spec
      name: (type_identifier) @name
      type_parameters: (type_parameter_list) @type_params
      type: (_) @type_def)) @generic_type
)

;; Const declarations
(
  (const_declaration
    (const_spec
      name: (identifier) @name
      type: (_)? @const_type
      value: (_)? @value)) @const
)

;; Var declarations
(
  (var_declaration
    (var_spec
      name: (identifier) @name
      type: (_)? @var_type
      value: (_)? @value)) @variable
)

;; Short variable declarations
(
  (short_var_declaration
    left: (expression_list
      (identifier) @var_name)) @short_var
)

;; Exported functions (capitalized)
(
  (function_declaration
    name: (identifier) @name @exported) @function
  (#match? @exported "^[A-Z]")
)

;; Exported types
(
  (type_declaration
    (type_spec
      name: (type_identifier) @name @exported)) @type
  (#match? @exported "^[A-Z]")
)

;; Interface method specs
(
  (method_spec
    name: (field_identifier) @name
    parameters: (parameter_list) @signature
    result: (_)? @return_type) @interface_method
)

;; Defer statements
(
  (defer_statement
    (call_expression
      function: (_) @call)) @defer
)

;; Go statements (goroutines)
(
  (go_statement
    (call_expression
      function: (_) @call)) @goroutine
)
