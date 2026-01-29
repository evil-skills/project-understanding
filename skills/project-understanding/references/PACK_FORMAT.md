# Pack Format Specification

This document defines the schema and structure for all "pack" outputs in the Project Understanding Interface (PUI). Packs are self-contained, token-budgeted views of codebase information designed for consumption by LLMs and developers.

## Overview

Packs provide structured, navigable representations of code:

- **RepoMapPack**: High-level codebase overview
- **ZoomPack**: Deep-dive into a specific file or symbol
- **ImpactPack**: Analysis of change impact and affected areas

All packs follow consistent principles:
- Markdown-first (human readable)
- JSON option (machine parsable)
- Strict token budgeting with hard truncation
- "More available" pointers for navigation
- Hierarchical structure with clear sections

---

## Token Budgeting Rules

### Budget Allocation

| Pack Type | Default Budget | Max Budget |
|-----------|---------------|------------|
| RepoMapPack | 8,000 tokens | 16,000 tokens |
| ZoomPack | 4,000 tokens | 8,000 tokens |
| ImpactPack | 6,000 tokens | 12,000 tokens |

### Truncation Strategy

1. **Hard truncation**: Content exceeding budget is cut off, not compressed
2. **Section preservation**: Truncate at section boundaries when possible
3. **Priority order**: Later sections are truncated first
4. **More pointers**: When truncating, add `[N more items available via zoom]`

### Truncation Algorithm

```
1. Calculate total estimated tokens
2. If within budget: return full content
3. If over budget:
   a. Remove lowest-priority sections entirely
   b. Within remaining sections, truncate lists/items
   c. Add "more available" pointer with count
   d. Ensure metadata section is never truncated
```

---

## RepoMapPack Schema

High-level overview of the entire codebase or a major subsystem.

### Sections (in order)

#### 1. Header
```markdown
# RepoMap: {project_name}

Generated: {ISO8601_timestamp}
Path: {root_path}
Budget: {used_tokens}/{max_tokens} tokens
```

#### 2. Summary
```markdown
## Summary

- **Total Files**: {N}
- **Total Symbols**: {N} ({N} functions, {N} classes, {N} interfaces)
- **Languages**: {lang1}, {lang2}, ...
- **Entry Points**: {file1}, {file2}
```

#### 3. Directory Structure
```markdown
## Directory Structure

```
src/
  components/
    Button.tsx        [Exported: Button, ButtonProps]
    Input.tsx         [Exported: Input, InputProps]
  utils/
    helpers.ts        [Exported: formatDate, parseJSON]
```
```

#### 4. Module Dependencies
```markdown
## Module Dependencies

### src/components/Button.tsx
- Imports: react, ./styles, ../utils/helpers
- Imported by: src/pages/Home.tsx, src/pages/Profile.tsx

### src/utils/helpers.ts
- Imports: date-fns
- Imported by: [5 files - see zoom for full list]
```

#### 5. Symbol Index
```markdown
## Symbol Index

### Functions
- `formatDate(date: Date, fmt: string): string` @ src/utils/helpers.ts:42
- `parseJSON<T>(json: string): T` @ src/utils/helpers.ts:67

### Classes
- `AuthService` @ src/services/auth.ts:15
  - Methods: login, logout, refreshToken

### Interfaces
- `UserProfile` @ src/types/user.ts:8
```

#### 6. Key Relationships
```markdown
## Key Relationships

```
AuthController -> AuthService -> UserRepository
                -> TokenService
                -> EmailService
```
```

#### 7. Metadata
```markdown
---
Schema Version: 1.0.0
Index Version: {index_hash}
More Available: Use `pui zoom <symbol>` for full details
```

### Example: Small RepoMapPack

```markdown
# RepoMap: tiny-utils

Generated: 2026-01-29T10:30:00Z
Path: /home/user/tiny-utils
Budget: 523/4000 tokens

## Summary

- **Total Files**: 3
- **Total Symbols**: 8 (5 functions, 0 classes, 1 interface)
- **Languages**: TypeScript
- **Entry Points**: src/index.ts

## Directory Structure

```
src/
  index.ts          [Exported: formatDate, parseJSON, clamp]
  types.ts          [Exported: DateFormat]
  utils.ts          [Internal]
```

## Symbol Index

### Functions
- `formatDate(date: Date, format: DateFormat): string` @ src/index.ts:15
- `parseJSON<T>(json: string): T | null` @ src/index.ts:32
- `clamp(value: number, min: number, max: number): number` @ src/index.ts:48

### Interfaces
- `DateFormat` @ src/types.ts:5
  - type: 'short' | 'long' | 'iso'

---
Schema Version: 1.0.0
Index Version: abc123
```

### Example: Medium RepoMapPack (truncated)

```markdown
# RepoMap: web-dashboard

Generated: 2026-01-29T10:30:00Z
Path: /home/user/web-dashboard
Budget: 7842/8000 tokens ⚠️

## Summary

- **Total Files**: 147
- **Total Symbols**: 892 (412 functions, 89 classes, 156 interfaces)
- **Languages**: TypeScript, CSS, JSON
- **Entry Points**: src/main.tsx, src/server.ts

## Directory Structure

```
src/
  components/       [23 files]
  hooks/            [12 files]
  pages/            [18 files]
  services/         [8 files]
  types/            [15 files]
  utils/            [31 files]
```
[8 more directories available via zoom]

## Module Dependencies

### src/components/index.ts
- Exports: 156 symbols
- Imported by: [47 files]

### src/services/api.ts
- Imports: axios, ./config
- Imported by: [23 files]
[15 more modules available via zoom]

## Symbol Index

### Functions (showing 50 of 412)
- `useAuth(): AuthContext` @ src/hooks/useAuth.ts:12
- `fetchUser(id: string): Promise<User>` @ src/services/api.ts:45
- `validateEmail(email: string): boolean` @ src/utils/validation.ts:8
[362 more functions available via zoom]

### Classes (showing 20 of 89)
- `ApiClient` @ src/services/api.ts:78
- `AuthManager` @ src/services/auth.ts:22
[69 more classes available via zoom]

### Interfaces (showing 30 of 156)
- `User` @ src/types/user.ts:5
- `ApiResponse<T>` @ src/types/api.ts:12
[126 more interfaces available via zoom]

---
Schema Version: 1.0.0
Index Version: def456
More Available: Use `pui zoom <symbol>` for full details
```

---

## ZoomPack Schema

Deep-dive view into a specific file or symbol.

### Sections (in order)

#### 1. Header
```markdown
# Zoom: {symbol_name} ({symbol_type})

File: {file_path}:{line_number}
Generated: {ISO8601_timestamp}
Budget: {used_tokens}/{max_tokens} tokens
```

#### 2. Signature
```markdown
## Signature

```typescript
function parseJSON<T>(
  json: string,
  options?: ParseOptions
): T | null;
```
```

#### 3. Documentation
```markdown
## Documentation

Parse a JSON string into a typed object.

@param json - The JSON string to parse
@param options - Optional parsing configuration
@returns The parsed object, or null if parsing fails
@throws {SyntaxError} If JSON is malformed and options.strict is true

**Example:**
```typescript
const user = parseJSON<User>('{"name": "John"}');
```
```

#### 4. Skeleton
```markdown
## Skeleton

```typescript
function parseJSON<T>(json: string, options?: ParseOptions): T | null {
  // Validate input
  // Apply defaults
  // Parse with error handling
  // Return result
}
```
```

#### 5. Callers
```markdown
## Callers

| Caller | File | Context |
|--------|------|---------|
| `loadConfig` | src/config.ts:45 | Called during initialization |
| `restoreSession` | src/auth.ts:112 | Called on page load |
| `handleSubmit` | src/forms/Login.tsx:78 | Called on form submission |
```

#### 6. Callees
```markdown
## Callees

| Callee | File | Purpose |
|--------|------|---------|
| `JSON.parse` | builtin | Core parsing |
| `validateSchema` | src/validation.ts:23 | Schema validation |
| `logError` | src/utils/log.ts:15 | Error logging |
```

#### 7. Code Slice
```markdown
## Code Slice

```typescript
// src/utils/parse.ts:32-67
function parseJSON<T>(
  json: string,
  options?: ParseOptions
): T | null {
  if (!json || typeof json !== 'string') {
    logError('Invalid input to parseJSON');
    return null;
  }

  const opts = { ...DEFAULT_PARSE_OPTIONS, ...options };

  try {
    const parsed = JSON.parse(json);
    if (opts.schema) {
      return validateSchema<T>(parsed, opts.schema) ? parsed : null;
    }
    return parsed as T;
  } catch (err) {
    if (opts.strict) throw err;
    logError('JSON parse failed', err);
    return null;
  }
}
```
```

#### 8. Related Symbols
```markdown
## Related Symbols

- `ParseOptions` @ src/types/parse.ts:8
- `validateSchema` @ src/validation.ts:23
- `DEFAULT_PARSE_OPTIONS` @ src/utils/parse.ts:12
```

#### 9. Metadata
```markdown
---
Schema Version: 1.0.0
Symbol ID: {unique_symbol_id}
Last Modified: {timestamp}
Test Coverage: 87% (see src/utils/parse.test.ts)
```

### Example: Small ZoomPack

```markdown
# Zoom: formatDate (function)

File: src/utils/date.ts:15
Generated: 2026-01-29T10:30:00Z
Budget: 423/4000 tokens

## Signature

```typescript
function formatDate(
  date: Date,
  format: 'short' | 'long' | 'iso'
): string;
```

## Documentation

Format a Date object into a string representation.

@param date - The date to format
@param format - The desired output format
@returns Formatted date string

**Example:**
```typescript
formatDate(new Date(), 'short'); // "01/29/2026"
formatDate(new Date(), 'long');  // "January 29, 2026"
```

## Skeleton

```typescript
function formatDate(date: Date, format: DateFormat): string {
  // Validate date
  // Select formatter
  // Return formatted string
}
```

## Callers

| Caller | File | Context |
|--------|------|---------|
| `UserProfile` | src/components/Profile.tsx:34 | Display join date |
| `ReportHeader` | src/reports/Header.tsx:12 | Report generation date |

## Code Slice

```typescript
// src/utils/date.ts:15-28
function formatDate(date: Date, format: DateFormat): string {
  if (!(date instanceof Date) || isNaN(date.getTime())) {
    return 'Invalid Date';
  }

  switch (format) {
    case 'short':
      return date.toLocaleDateString();
    case 'long':
      return date.toLocaleDateString(undefined, { 
        month: 'long', day: 'numeric', year: 'numeric' 
      });
    case 'iso':
      return date.toISOString().split('T')[0];
    default:
      return String(date);
  }
}
```

---
Schema Version: 1.0.0
Symbol ID: date.ts:formatDate
```

### Example: Medium ZoomPack (truncated)

```markdown
# Zoom: AuthService (class)

File: src/services/auth.ts:22
Generated: 2026-01-29T10:30:00Z
Budget: 3987/4000 tokens ⚠️

## Signature

```typescript
class AuthService {
  constructor(config: AuthConfig);
  login(credentials: Credentials): Promise<AuthResult>;
  logout(): Promise<void>;
  refreshToken(): Promise<string>;
  validateSession(): Promise<boolean>;
  // ... 8 more methods
}
```

## Documentation

Core authentication service handling user login, logout, and session management.

Supports multiple auth strategies: password, OAuth, SAML.
Implements token refresh and automatic retry logic.

## Skeleton

```typescript
class AuthService {
  private tokenManager: TokenManager;
  private config: AuthConfig;
  
  constructor(config: AuthConfig) {
    // Initialize token manager
    // Setup interceptors
  }
  
  async login(credentials: Credentials): Promise<AuthResult> {
    // Validate credentials
    // Call auth endpoint
    // Store tokens
    // Emit event
  }
  
  async logout(): Promise<void> {
    // Invalidate server session
    // Clear local storage
    // Emit event
  }
  
  // ... 8 more methods
}
```

## Callers

| Caller | File | Context |
|--------|------|---------|
| `LoginPage` | src/pages/Login.tsx:45 | User login flow |
| `AuthProvider` | src/context/Auth.tsx:78 | React context |
| `Header` | src/components/Header.tsx:23 | Logout button |
| `ApiClient` | src/services/api.ts:156 | Token refresh |
[12 more callers available via zoom]

## Callees

| Callee | File | Purpose |
|--------|------|---------|
| `TokenManager` | src/services/token.ts:15 | Token storage |
| `ApiClient.post` | src/services/api.ts:89 | HTTP requests |
| `EventEmitter.emit` | src/utils/events.ts:34 | Event dispatch |
[8 more callees available via zoom]

## Code Slice

```typescript
// src/services/auth.ts:45-98
async login(credentials: Credentials): Promise<AuthResult> {
  try {
    const response = await this.api.post('/auth/login', credentials);
    
    if (!response.success) {
      throw new AuthError(response.error);
    }

    await this.tokenManager.setTokens(response.tokens);
    this.emit('login', { user: response.user });
    
    return {
      user: response.user,
      sessionId: response.sessionId
    };
  } catch (error) {
    this.emit('loginFailed', { error });
    throw error;
  }
}

async logout(): Promise<void> {
  try {
    await this.api.post('/auth/logout');
  } finally {
    await this.tokenManager.clear();
    this.emit('logout');
  }
}
```
[6 more methods truncated - use `pui zoom AuthService#refreshToken` for details]

## Related Symbols

- `AuthConfig` @ src/types/auth.ts:12
- `Credentials` @ src/types/auth.ts:28
- `TokenManager` @ src/services/token.ts:15
- `AuthError` @ src/errors/auth.ts:8

---
Schema Version: 1.0.0
Symbol ID: auth.ts:AuthService
```

---

## ImpactPack Schema

Analysis of code change impact showing affected areas.

### Sections (in order)

#### 1. Header
```markdown
# Impact Analysis

Generated: {ISO8601_timestamp}
Base: {git_ref_base}
Compare: {git_ref_compare}
Budget: {used_tokens}/{max_tokens} tokens
```

#### 2. Changed Items Summary
```markdown
## Changed Items

| Item | Type | Change | Lines |
|------|------|--------|-------|
| `src/auth.ts` | File | Modified | +45, -12 |
| `AuthService.login` | Method | Modified | +23, -8 |
| `TokenManager` | Class | Added | +156 |
```

#### 3. Upstream Dependencies
```markdown
## Upstream Dependencies (Direct Callers)

Items that call the changed code:

| Item | File | Relationship | Risk |
|------|------|--------------|------|
| `LoginPage` | src/pages/Login.tsx | Calls AuthService.login | HIGH |
| `AuthProvider` | src/context/Auth.tsx | Uses AuthService | MEDIUM |
| `Header.logout` | src/components/Header.tsx | Calls AuthService.logout | LOW |
```

#### 4. Downstream Dependencies
```markdown
## Downstream Dependencies (Transitive Impact)

Items potentially affected through dependency chains:

| Item | File | Path Length | Risk |
|------|------|-------------|------|
| `ProtectedRoute` | src/routes/Protected.tsx | 2 hops | MEDIUM |
| `UserDashboard` | src/pages/Dashboard.tsx | 3 hops | LOW |
```

#### 5. Test Impact
```markdown
## Test Impact

| Test File | Tests Affected | Coverage |
|-----------|----------------|----------|
| auth.test.ts | 12 tests | 87% → ? |
| login.e2e.ts | 3 tests | Unknown |

### Missing Test Coverage

The following changed items lack test coverage:

- `AuthService.refreshToken` (new method)
- Error handling in `AuthService.login` (new branch)
```

#### 6. Risk Assessment
```markdown
## Risk Assessment

| Category | Risk Level | Details |
|----------|------------|---------|
| Breaking Changes | HIGH | Signature change in public API |
| Test Coverage | MEDIUM | 3 new paths untested |
| Dependencies | MEDIUM | 12 direct callers affected |

### Recommended Actions

1. Update `LoginPage` to handle new return type
2. Add tests for `TokenManager` (156 lines, 0 tests)
3. Verify backward compatibility for `AuthService.login`
```

#### 7. Ranked Files for Review
```markdown
## Files Requiring Review (Ranked by Risk)

1. **src/auth.ts** - Direct changes, public API
2. **src/pages/Login.tsx** - Direct caller, high traffic
3. **src/context/Auth.tsx** - Core dependency
4. **src/routes/Protected.tsx** - Security-critical
[12 more files available via zoom]
```

#### 8. Metadata
```markdown
---
Schema Version: 1.0.0
Analysis Depth: 3 levels
Confidence: 92%
Generated by: pui impact {args}
```

### Example: Small ImpactPack

```markdown
# Impact Analysis

Generated: 2026-01-29T10:30:00Z
Base: HEAD~1
Compare: HEAD
Budget: 892/6000 tokens

## Changed Items

| Item | Type | Change | Lines |
|------|------|--------|-------|
| `formatDate` | Function | Modified | +8, -3 |

## Upstream Dependencies

| Item | File | Relationship | Risk |
|------|------|--------------|------|
| `UserProfile` | src/components/Profile.tsx | Calls formatDate | LOW |
| `ReportHeader` | src/reports/Header.tsx | Calls formatDate | LOW |

## Risk Assessment

| Category | Risk Level | Details |
|----------|------------|---------|
| Breaking Changes | LOW | Added optional parameter |
| Test Coverage | LOW | Existing tests cover change |

### Recommended Actions

1. No action required - backward compatible change

## Files Requiring Review

1. **src/utils/date.ts** - Direct changes

---
Schema Version: 1.0.0
Analysis Depth: 3 levels
```

### Example: Medium ImpactPack

```markdown
# Impact Analysis

Generated: 2026-01-29T10:30:00Z
Base: main
Compare: feature/auth-refactor
Budget: 5847/6000 tokens

## Changed Items

| Item | Type | Change | Lines |
|------|------|--------|-------|
| `AuthService` | Class | Modified | +89, -45 |
| `TokenManager` | Class | Added | +156 |
| `auth.types.ts` | File | Modified | +34, -12 |
| `useAuth` | Hook | Modified | +23, -15 |

## Upstream Dependencies

| Item | File | Relationship | Risk |
|------|------|--------------|------|
| `LoginPage` | src/pages/Login.tsx | Calls AuthService.login | HIGH |
| `AuthProvider` | src/context/Auth.tsx | Uses AuthService | HIGH |
| `Header.logout` | src/components/Header.tsx | Calls AuthService.logout | MEDIUM |
| `ApiClient` | src/services/api.ts | Uses token refresh | HIGH |
| `ProtectedRoute` | src/routes/Protected.tsx | Depends on auth state | MEDIUM |

## Downstream Dependencies

| Item | File | Path Length | Risk |
|------|------|-------------|------|
| `UserDashboard` | src/pages/Dashboard.tsx | 2 hops | MEDIUM |
| `SettingsPage` | src/pages/Settings.tsx | 2 hops | LOW |
| `AdminPanel` | src/admin/Panel.tsx | 3 hops | LOW |
[8 more items available via zoom]

## Test Impact

| Test File | Tests Affected | Coverage Change |
|-----------|----------------|-----------------|
| auth.test.ts | 12 tests | 87% → 82% |
| token.test.ts | 0 tests → 8 tests | 0% → 95% |
| login.e2e.ts | 3 tests | Unknown |
| useAuth.test.ts | 5 tests | 76% → ? |

### Missing Test Coverage

- `AuthService.refreshToken` error handling (new)
- `TokenManager` persistence edge cases (new class)
- OAuth flow integration (modified)

## Risk Assessment

| Category | Risk Level | Details |
|----------|------------|---------|
| Breaking Changes | HIGH | Return type changed from User to AuthResult |
| Test Coverage | MEDIUM | 45 lines of new code, 20% covered |
| Dependencies | HIGH | 5 critical paths affected |
| Security | MEDIUM | Token handling logic modified |

### Recommended Actions

1. **CRITICAL**: Update `LoginPage` to handle new `AuthResult` return type
2. **HIGH**: Add unit tests for `TokenManager` (156 lines, minimal coverage)
3. **HIGH**: Verify OAuth callback handling still works
4. **MEDIUM**: Update API documentation for new return types
5. **MEDIUM**: Run E2E tests on staging before deploy

## Files Requiring Review (Ranked by Risk)

1. **src/services/auth.ts** - Core auth logic, public API changes
2. **src/pages/Login.tsx** - High-traffic, affected by API change
3. **src/services/api.ts** - Token refresh integration
4. **src/context/Auth.tsx** - Auth state management
5. **src/routes/Protected.tsx** - Security-critical route guard
6. **src/services/token.ts** - New token management logic
7. **src/hooks/useAuth.ts** - React integration layer
8. **src/types/auth.ts** - Type definitions
[12 more files available via zoom]

---
Schema Version: 1.0.0
Analysis Depth: 3 levels
Confidence: 89%
Generated by: pui impact --diff main..feature/auth-refactor
```

---

## JSON Format

All packs can be serialized to JSON. The structure mirrors the Markdown sections:

### RepoMapPack JSON Schema

```json
{
  "schema_version": "1.0.0",
  "type": "repomap",
  "metadata": {
    "project_name": "string",
    "generated_at": "ISO8601",
    "root_path": "string",
    "budget": { "used": 7842, "max": 8000 }
  },
  "summary": {
    "total_files": 147,
    "total_symbols": 892,
    "functions": 412,
    "classes": 89,
    "interfaces": 156,
    "languages": ["TypeScript", "CSS"],
    "entry_points": ["src/main.tsx"]
  },
  "directory_structure": [...],
  "dependencies": [...],
  "symbols": {
    "functions": [...],
    "classes": [...],
    "interfaces": [...]
  },
  "relationships": [...],
  "truncated": {
    "functions": 362,
    "classes": 69,
    "note": "Use pui zoom for full details"
  }
}
```

### ZoomPack JSON Schema

```json
{
  "schema_version": "1.0.0",
  "type": "zoom",
  "metadata": {
    "symbol_name": "AuthService",
    "symbol_type": "class",
    "file_path": "src/services/auth.ts",
    "line_number": 22,
    "generated_at": "ISO8601",
    "budget": { "used": 3987, "max": 4000 }
  },
  "signature": "string",
  "documentation": "string",
  "skeleton": "string",
  "callers": [...],
  "callees": [...],
  "code_slice": "string",
  "related_symbols": [...],
  "truncated": {
    "methods": 6,
    "callers": 12,
    "note": "Use pui zoom for full details"
  }
}
```

### ImpactPack JSON Schema

```json
{
  "schema_version": "1.0.0",
  "type": "impact",
  "metadata": {
    "generated_at": "ISO8601",
    "base_ref": "main",
    "compare_ref": "feature/auth-refactor",
    "budget": { "used": 5847, "max": 6000 },
    "confidence": 0.89
  },
  "changed_items": [...],
  "upstream_dependencies": [...],
  "downstream_dependencies": [...],
  "test_impact": {
    "affected_tests": [...],
    "missing_coverage": [...]
  },
  "risk_assessment": {
    "breaking_changes": "HIGH",
    "test_coverage": "MEDIUM",
    "dependencies": "HIGH",
    "recommendations": [...]
  },
  "files_for_review": [...],
  "truncated": {
    "downstream": 8,
    "files": 12,
    "note": "Use pui zoom for full details"
  }
}
```

---

## Version History

- **1.0.0** (2026-01-29): Initial schema definition
