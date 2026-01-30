"""
Dataflow heuristics for analyzing function effects and side effects.

Provides analysis of:
- Database operations (reads/writes)
- File system operations
- Network operations
- Global mutations
- Exception throwing patterns
"""

import re
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto


class EffectType(Enum):
    """Types of effects a function can have."""
    DB_READ = auto()
    DB_WRITE = auto()
    DB_DELETE = auto()
    FILE_READ = auto()
    FILE_WRITE = auto()
    FILE_DELETE = auto()
    NETWORK_READ = auto()
    NETWORK_WRITE = auto()
    GLOBAL_MUTATION = auto()
    THROWS_EXCEPTION = auto()
    PURE = auto()


@dataclass
class Effect:
    """Represents a single effect."""
    type: EffectType
    description: str
    confidence: float = 1.0
    line_number: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': self.type.name,
            'description': self.description,
            'confidence': round(self.confidence, 2),
            'line': self.line_number
        }


@dataclass
class FunctionEffects:
    """Effects summary for a function."""
    function_name: str
    file_path: str
    line_start: int
    effects: List[Effect] = field(default_factory=list)
    is_pure: bool = True
    throws_exceptions: List[str] = field(default_factory=list)
    global_mutations: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'function': self.function_name,
            'file': self.file_path,
            'line': self.line_start,
            'is_pure': self.is_pure,
            'effects': [e.to_dict() for e in self.effects],
            'throws': self.throws_exceptions,
            'global_mutations': self.global_mutations
        }
    
    def to_text(self) -> str:
        """Format as readable text."""
        lines = [
            f"## {self.function_name}()",
            f"",
            f"**File**: `{self.file_path}:{self.line_start}`",
            f"**Pure**: {'Yes' if self.is_pure else 'No'}",
            f""
        ]
        
        if self.effects:
            lines.append("**Effects**:")
            for effect in self.effects:
                lines.append(f"  - {effect.type.name}: {effect.description}")
            lines.append("")
        
        if self.throws_exceptions:
            lines.append(f"**Throws**: {', '.join(self.throws_exceptions)}")
            lines.append("")
        
        if self.global_mutations:
            lines.append(f"**Global Mutations**: {', '.join(self.global_mutations)}")
            lines.append("")
        
        return '\n'.join(lines)


class DataflowAnalyzer:
    """Analyzes code for side effects and data flow."""
    
    # Database operation patterns
    DB_PATTERNS = {
        EffectType.DB_READ: [
            r'\.query\(',
            r'\.select\(',
            r'\.find\(',
            r'\.get\(',
            r'\.fetch\(',
            r'\.all\(',
            r'\.filter\(',
            r'\.where\(',
            r'execute\(.*SELECT',
            r'\.read\(',
            r'session\.query',
            r'objects\.filter',
        ],
        EffectType.DB_WRITE: [
            r'\.save\(',
            r'\.create\(',
            r'\.insert\(',
            r'\.update\(',
            r'\.bulk_create',
            r'execute\(.*INSERT',
            r'execute\(.*UPDATE',
            r'\.add\(',
            r'\.commit\(',
        ],
        EffectType.DB_DELETE: [
            r'\.delete\(',
            r'\.remove\(',
            r'\.destroy\(',
            r'execute\(.*DELETE',
        ],
    }
    
    # File operation patterns
    FILE_PATTERNS = {
        EffectType.FILE_READ: [
            r'open\([^,]+[,"\']r',
            r'\.read\(',
            r'\.readline',
            r'\.readlines',
            r'\.load\(',
            r'json\.load',
            r'yaml\.load',
            r'pickle\.load',
            r'\.from_file',
            r'Path\([^)]+\)\.read',
        ],
        EffectType.FILE_WRITE: [
            r'open\([^,]+[,"\']w',
            r'open\([^,]+[,"\']a',
            r'\.write\(',
            r'\.dump\(',
            r'json\.dump',
            r'yaml\.dump',
            r'pickle\.dump',
            r'\.to_file',
            r'Path\([^)]+\)\.write',
        ],
        EffectType.FILE_DELETE: [
            r'os\.remove\(',
            r'os\.unlink\(',
            r'shutil\.rmtree',
            r'Path\([^)]+\)\.unlink',
        ],
    }
    
    # Network operation patterns
    NETWORK_PATTERNS = {
        EffectType.NETWORK_READ: [
            r'requests\.get\(',
            r'requests\.post\(',
            r'\.get\([^)]*http',
            r'\.fetch\(',
            r'urllib\.request',
            r'\.recv\(',
            r'socket\.',
            r'httpx\.get',
            r'httpx\.post',
        ],
        EffectType.NETWORK_WRITE: [
            r'requests\.post\(',
            r'requests\.put\(',
            r'requests\.patch\(',
            r'\.send\(',
            r'\.emit\(',
            r'\.broadcast',
            r'\.publish',
        ],
    }
    
    # Global mutation patterns
    GLOBAL_PATTERNS = [
        r'global\s+\w+',
        r'\w+\s*=\s*\[.*\]',  # List assignment at module level
        r'\w+\s*=\s*\{.*\}',  # Dict assignment at module level
        r'os\.environ\[',
        r'sys\.path',
        r'settings\.',
        r'CONFIG\[',
    ]
    
    # Exception patterns
    EXCEPTION_PATTERNS = [
        r'raise\s+(\w+)',
        r'raise\s+\w+\s*\(',
        r'throw\s+new',
        r'\.catch\(',
    ]
    
    def __init__(self, file_path: str, content: str):
        self.file_path = file_path
        self.content = content
        self.lines = content.split('\n')
    
    def analyze_function(self, function_name: str, start_line: int, end_line: int) -> FunctionEffects:
        """Analyze a function for effects."""
        func_content = '\n'.join(self.lines[start_line-1:end_line])
        
        effects = []
        throws = []
        global_mutations = []
        is_pure = True
        
        # Check database operations
        for effect_type, patterns in self.DB_PATTERNS.items():
            for pattern in patterns:
                for match in re.finditer(pattern, func_content):
                    effects.append(Effect(
                        type=effect_type,
                        description=f"Database {effect_type.name.split('_')[1].lower()} operation detected",
                        confidence=0.8,
                        line_number=self._get_line_number(match.start(), start_line)
                    ))
                    is_pure = False
        
        # Check file operations
        for effect_type, patterns in self.FILE_PATTERNS.items():
            for pattern in patterns:
                for match in re.finditer(pattern, func_content):
                    effects.append(Effect(
                        type=effect_type,
                        description=f"File {effect_type.name.split('_')[1].lower()} operation detected",
                        confidence=0.9,
                        line_number=self._get_line_number(match.start(), start_line)
                    ))
                    is_pure = False
        
        # Check network operations
        for effect_type, patterns in self.NETWORK_PATTERNS.items():
            for pattern in patterns:
                for match in re.finditer(pattern, func_content):
                    effects.append(Effect(
                        type=effect_type,
                        description=f"Network {effect_type.name.split('_')[1].lower()} operation detected",
                        confidence=0.85,
                        line_number=self._get_line_number(match.start(), start_line)
                    ))
                    is_pure = False
        
        # Check global mutations
        for pattern in self.GLOBAL_PATTERNS:
            for match in re.finditer(pattern, func_content):
                mutation = func_content[max(0, match.start()-20):min(len(func_content), match.end()+20)]
                global_mutations.append(mutation.strip())
                effects.append(Effect(
                    type=EffectType.GLOBAL_MUTATION,
                    description=f"Global state mutation: {mutation[:40]}...",
                    confidence=0.7,
                    line_number=self._get_line_number(match.start(), start_line)
                ))
                is_pure = False
        
        # Check exception throwing
        for pattern in self.EXCEPTION_PATTERNS:
            for match in re.finditer(pattern, func_content):
                exc_match = re.search(r'raise\s+(\w+)', func_content[match.start():match.start()+50])
                if exc_match:
                    throws.append(exc_match.group(1))
                effects.append(Effect(
                    type=EffectType.THROWS_EXCEPTION,
                    description="Exception throwing path detected",
                    confidence=0.9,
                    line_number=self._get_line_number(match.start(), start_line)
                ))
        
        # If no effects detected, mark as pure
        if is_pure and not effects:
            effects.append(Effect(
                type=EffectType.PURE,
                description="No side effects detected",
                confidence=0.6  # Lower confidence since it's absence of evidence
            ))
        
        return FunctionEffects(
            function_name=function_name,
            file_path=self.file_path,
            line_start=start_line,
            effects=effects,
            is_pure=is_pure,
            throws_exceptions=list(set(throws)),
            global_mutations=list(set(global_mutations))
        )
    
    def _get_line_number(self, char_offset: int, base_line: int) -> int:
        """Get line number from character offset."""
        # Simple approximation
        lines_before = self.content[:char_offset].count('\n')
        return base_line + lines_before


@dataclass
class RepositoryDataflow:
    """Dataflow analysis for entire repository."""
    functions: List[FunctionEffects] = field(default_factory=list)
    
    def get_pure_functions(self) -> List[FunctionEffects]:
        """Get all pure functions."""
        return [f for f in self.functions if f.is_pure]
    
    def get_functions_with_effect(self, effect_type: EffectType) -> List[FunctionEffects]:
        """Get functions with specific effect type."""
        return [f for f in self.functions if any(e.type == effect_type for e in f.effects)]
    
    def get_db_functions(self) -> List[FunctionEffects]:
        """Get all database-related functions."""
        db_effects = {EffectType.DB_READ, EffectType.DB_WRITE, EffectType.DB_DELETE}
        return [f for f in self.functions if any(e.type in db_effects for e in f.effects)]
    
    def get_io_functions(self) -> List[FunctionEffects]:
        """Get all I/O functions (file + network)."""
        io_effects = {EffectType.FILE_READ, EffectType.FILE_WRITE, EffectType.NETWORK_READ, EffectType.NETWORK_WRITE}
        return [f for f in self.functions if any(e.type in io_effects for e in f.effects)]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'total_functions': len(self.functions),
            'pure_functions': len(self.get_pure_functions()),
            'db_functions': len(self.get_db_functions()),
            'io_functions': len(self.get_io_functions()),
            'functions': [f.to_dict() for f in self.functions]
        }
    
    def to_text(self) -> str:
        """Format as readable report."""
        lines = [
            "# Dataflow Analysis Report",
            "",
            f"**Total Functions**: {len(self.functions)}",
            f"**Pure Functions**: {len(self.get_pure_functions())}",
            f"**Database Functions**: {len(self.get_db_functions())}",
            f"**I/O Functions**: {len(self.get_io_functions())}",
            ""
        ]
        
        # Group by effect type
        effect_groups = {}
        for func in self.functions:
            for effect in func.effects:
                if effect.type not in effect_groups:
                    effect_groups[effect.type] = []
                effect_groups[effect.type].append(func)
        
        lines.append("## Effect Summary")
        lines.append("")
        for effect_type, funcs in sorted(effect_groups.items(), key=lambda x: len(x[1]), reverse=True):
            lines.append(f"- **{effect_type.name}**: {len(funcs)} functions")
        
        lines.append("")
        lines.append("## Detailed Function Analysis")
        lines.append("")
        
        for func in self.functions[:50]:  # Limit output
            lines.append(func.to_text())
        
        return '\n'.join(lines)


def analyze_dataflow(file_path: str, content: str, symbols: List[Dict[str, Any]]) -> RepositoryDataflow:
    """Analyze dataflow for all functions in a file."""
    analyzer = DataflowAnalyzer(file_path, content)
    result = RepositoryDataflow()
    
    for symbol in symbols:
        if symbol.get('kind') in ('function', 'method'):
            func_effects = analyzer.analyze_function(
                function_name=symbol['name'],
                start_line=symbol.get('line_start', 1),
                end_line=symbol.get('line_end', symbol.get('line_start', 1) + 10)
            )
            result.functions.append(func_effects)
    
    return result
