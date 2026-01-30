;; JavaScript Tree-sitter queries for Project Understanding
;; Captures: functions, methods, classes, imports, calls

;; Function declarations
(
  (function_declaration
    name: (identifier) @name
    parameters: (formal_parameters) @signature) @function
)

;; Function expressions
(
  (function_expression
    name: (identifier)? @name
    parameters: (formal_parameters) @signature) @function
)

;; Arrow functions
(
  (arrow_function
    parameters: (_) @signature) @function
)

;; Method definitions in classes
(
  (method_definition
    name: (property_identifier) @name
    parameters: (formal_parameters) @signature) @method
)

;; Class declarations
(
  (class_declaration
    name: (identifier) @name
    super_class: (identifier)? @superclass) @class
)

;; Class expressions
(
  (class_expression
    name: (identifier)? @name
    super_class: (identifier)? @superclass) @class
)

;; Constructor
(
  (method_definition
    name: (property_identifier) @name
    parameters: (formal_parameters) @signature) @constructor
  (#eq? @name "constructor")
)

;; Getters
(
  (method_definition
    "get"
    name: (property_identifier) @name) @getter
)

;; Setters
(
  (method_definition
    "set"
    name: (property_identifier) @name
    parameters: (formal_parameters) @signature) @setter
)

;; Async functions
(
  (function_declaration
    "async"
    name: (identifier) @name
    parameters: (formal_parameters) @signature) @function
)

;; Generator functions
(
  (function_declaration
    "*" @generator_marker
    name: (identifier) @name
    parameters: (formal_parameters) @signature) @function
)

;; Import statements
(import_statement) @import

;; Named imports
(
  (import_statement
    (import_clause
      (named_imports
        (import_specifier
          name: (identifier) @import_name
          alias: (identifier)? @import_alias))))
)

;; Default imports
(
  (import_statement
    (import_clause
      (identifier) @import_default))
)

;; Namespace imports
(
  (import_statement
    (import_clause
      (namespace_import
        (identifier) @namespace)))
)

;; Call expressions
(call_expression
  function: (_) @call) @call_expr

;; Method calls (obj.method())
(call_expression
  function: (member_expression
    object: (_) @object
    property: (property_identifier) @method_name) @call)

;; New expressions
(new_expression
  constructor: (identifier) @constructor) @new_call

;; Variable declarations (for tracking)
(
  (variable_declaration
    (variable_declarator
      name: (identifier) @variable_name))
)

;; Exported functions
(
  (export_statement
    (function_declaration
      name: (identifier) @name) @function)
)

;; Exported classes
(
  (export_statement
    (class_declaration
      name: (identifier) @name) @class)
)
