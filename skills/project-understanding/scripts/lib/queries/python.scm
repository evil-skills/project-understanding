;; Python Tree-sitter queries for Project Understanding
;; Captures: functions, methods, classes, imports, calls

;; Function definitions
(
  (function_definition
    name: (identifier) @name
    parameters: (parameters) @signature) @function
  (#not-parent-type? @function class_definition)
)

;; Method definitions (inside classes)
(
  (function_definition
    name: (identifier) @name
    parameters: (parameters) @signature) @method
  (#parent-type? @method class_definition)
)

;; Class definitions
(
  (class_definition
    name: (identifier) @name
    superclasses: (argument_list)? @superclasses) @class
)

;; Decorated functions
(
  (decorated_definition
    definition: (function_definition
      name: (identifier) @name
      parameters: (parameters) @signature) @function)
)

;; Async functions
(
  (function_definition
    "async"
    name: (identifier) @name
    parameters: (parameters) @signature) @function
)

;; Lambda functions (captured but marked as lambda)
(lambda
  parameters: (lambda_parameters)? @signature) @lambda

;; Docstrings
(
  (function_definition
    body: (block
      (expression_statement
        (string) @docstring) .))
)

(
  (class_definition
    body: (block
      (expression_statement
        (string) @docstring) .))
)

;; Import statements
(import_statement) @import
(import_from_statement) @import

;; Call expressions
(call
  function: (_) @call) @call_expr

;; Attribute calls (obj.method())
(call
  function: (attribute
    object: (_) @object
    attribute: (identifier) @method_name) @call)

;; Module-level variable assignments (potential constants)
(
  (module
    (expression_statement
      (assignment
        left: (identifier) @name) @variable))
)
