;; TypeScript Tree-sitter queries for Project Understanding
;; Captures: functions, methods, classes, interfaces, types, imports, calls

;; Function declarations
(
  (function_declaration
    name: (identifier) @name
    parameters: (formal_parameters) @signature
    type: (type_annotation)? @return_type) @function
)

;; Function expressions
(
  (function_expression
    name: (identifier)? @name
    parameters: (formal_parameters) @signature
    type: (type_annotation)? @return_type) @function
)

;; Arrow functions
(
  (arrow_function
    parameters: (_) @signature
    type: (type_annotation)? @return_type) @function
)

;; Method definitions
(
  (method_definition
    name: (property_identifier) @name
    parameters: (formal_parameters) @signature
    type: (type_annotation)? @return_type) @method
)

;; Class declarations
(
  (class_declaration
    name: (type_identifier) @name
    type_parameters: (type_parameters)? @type_params
    super_class: (identifier)? @superclass
    implements: (class_heritage)? @implements) @class
)

;; Class expressions
(
  (class_expression
    name: (type_identifier)? @name
    super_class: (identifier)? @superclass) @class
)

;; Interface declarations
(
  (interface_declaration
    name: (type_identifier) @name
    type_parameters: (type_parameters)? @type_params
    extends: (extends_type_clause)? @extends) @interface
)

;; Type alias declarations
(
  (type_alias_declaration
    name: (type_identifier) @name
    type_parameters: (type_parameters)? @type_params
    value: (_) @type_value) @type_alias
)

;; Abstract method
(
  (method_definition
    "abstract"
    name: (property_identifier) @name
    parameters: (formal_parameters) @signature
    type: (type_annotation)? @return_type) @abstract_method
)

;; Abstract class
(
  (class_declaration
    "abstract"
    name: (type_identifier) @name) @abstract_class
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
    parameters: (formal_parameters) @signature
    type: (type_annotation)? @return_type) @function
)

;; Generator functions
(
  (function_declaration
    "*" @generator_marker
    name: (identifier) @name
    parameters: (formal_parameters) @signature) @function
)

;; Generic function
(
  (function_declaration
    name: (identifier) @name
    type_parameters: (type_parameters) @type_params) @generic_function
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

;; Type imports
(
  (import_statement
    "type"
    (import_clause
      (named_imports)))
)

;; Call expressions
(call_expression
  function: (_) @call) @call_expr

;; Method calls
(call_expression
  function: (member_expression
    object: (_) @object
    property: (property_identifier) @method_name) @call)

;; New expressions
(new_expression
  constructor: (identifier) @constructor) @new_call

;; Generic instantiation
(call_expression
  function: (identifier) @generic_call
  type_arguments: (type_arguments) @type_args)

;; Variable declarations
(
  (variable_declaration
    (variable_declarator
      name: (identifier) @variable_name
      type: (type_annotation)? @variable_type))
)

;; Exported declarations
(
  (export_statement
    (function_declaration
      name: (identifier) @name) @function)
)

(
  (export_statement
    (class_declaration
      name: (type_identifier) @name) @class)
)

(
  (export_statement
    (interface_declaration
      name: (type_identifier) @name) @interface)
)

(
  (export_statement
    (type_alias_declaration
      name: (type_identifier) @name) @type_alias)
)

;; Enum declarations
(
  (enum_declaration
    name: (identifier) @name) @enum
)
