;; C/C++ Tree-sitter queries for Project Understanding
;; Captures: functions, methods, classes, structs, namespaces, imports, calls

;; Function definitions
(function_definition
  declarator: (function_declarator
    declarator: (identifier) @name
    parameters: (parameter_list) @signature) @function)

;; Method definitions (member functions)
(function_definition
  declarator: (field_identifier) @name @method)

;; Class and Struct definitions
(class_specifier
  name: (type_identifier) @name) @class

(struct_specifier
  name: (type_identifier) @name) @class

;; Namespace definitions
(namespace_definition
  name: (identifier) @name) @namespace

;; Include directives (best effort as imports)
(preproc_include
  path: [
    (string_literal)
    (system_lib_string)
  ] @import) @import_stmt

;; Call expressions
(call_expression
  function: (_) @call) @call_expr
