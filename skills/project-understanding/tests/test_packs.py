"""
Unit tests for the packs module.

Tests cover:
- RepoMapPackGenerator
- ZoomPackGenerator
- ImpactPackGenerator
- Token budget enforcement
- Focus subdirectory filtering
- Code slice loading
- Impact ranking
"""

import pytest
import tempfile
from pathlib import Path

from scripts.lib.packs import (
    RepoMapPack, ImpactPack,
    RepoMapPackGenerator, ZoomPackGenerator, ImpactPackGenerator,
    PackSection, repomap, zoom, impact
)
from scripts.lib.db import Database
from scripts.lib.tokens import estimate_tokens


class TestRepoMapPackGenerator:
    """Tests for RepoMapPack generator."""
    
    @pytest.fixture
    def generator_with_data(self):
        """Create generator with sample repository data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            db_path = repo_root / ".pui" / "index.sqlite"
            db_path.parent.mkdir(parents=True)
            
            db = Database(db_path)
            db.connect()
            
            # Create file structure
            files = [
                ("src/main.py", "python"),
                ("src/utils.py", "python"),
                ("src/core/app.py", "python"),
                ("tests/test_main.py", "python"),
                ("tests/test_utils.py", "python"),
                ("README.md", None),
            ]
            
            for i, (path, lang) in enumerate(files):
                file_id = db.add_file(path, i+1, 1000, f"hash{i}", lang)
                
                # Add some symbols
                db.add_symbol(file_id, f"func_{i}_a", "function", 1, 10,
                            signature=f"def func_{i}_a()")
                db.add_symbol(file_id, f"func_{i}_b", "function", 15, 25,
                            signature=f"def func_{i}_b()")
                if i == 0:  # main.py
                    db.add_symbol(file_id, "MainClass", "class", 30, 60,
                                signature="class MainClass:")
            
            db.commit()
            
            generator = RepoMapPackGenerator(repo_root, db)
            
            yield generator, repo_root
            
            db.close()
    
    def test_generate_basic(self, generator_with_data):
        """Should generate a basic RepoMapPack."""
        generator, repo_root = generator_with_data
        
        pack = generator.generate(budget_tokens=4000)
        
        assert isinstance(pack, RepoMapPack)
        assert pack.directory_tree
        assert len(pack.top_files) > 0
        assert pack.dependency_summary
    
    def test_directory_tree_structure(self, generator_with_data):
        """Directory tree should be properly formatted."""
        generator, repo_root = generator_with_data
        
        pack = generator.generate(budget_tokens=4000)
        
        # Should have tree structure markers
        assert "src" in pack.directory_tree
        assert "tests" in pack.directory_tree
        # Tree uses box drawing characters
        assert any(c in pack.directory_tree for c in ["├──", "└──", "│"])
    
    def test_top_files_ranked(self, generator_with_data):
        """Top files should be ranked by importance."""
        generator, repo_root = generator_with_data
        
        pack = generator.generate(budget_tokens=4000)
        
        assert len(pack.top_files) > 0
        # Files should have scores
        assert all('score' in f for f in pack.top_files)
        # Should be sorted by score descending
        scores = [f['score'] for f in pack.top_files]
        assert scores == sorted(scores, reverse=True)
    
    def test_file_symbols_included(self, generator_with_data):
        """Should include symbols for top files."""
        generator, repo_root = generator_with_data
        
        pack = generator.generate(budget_tokens=4000)
        
        assert len(pack.file_symbols) > 0
        
        # Check structure
        for path, symbols in pack.file_symbols.items():
            assert isinstance(symbols, list)
            if symbols:
                assert 'name' in symbols[0]
                assert 'kind' in symbols[0]
    
    def test_dependency_summary(self, generator_with_data):
        """Should include dependency summary."""
        generator, repo_root = generator_with_data
        
        pack = generator.generate(budget_tokens=4000)
        
        assert 'file_count' in pack.dependency_summary
        assert 'symbol_count' in pack.dependency_summary
        assert pack.dependency_summary['file_count'] >= 6
    
    def test_focus_subdirectory(self, generator_with_data):
        """Focus option should filter to subdirectory."""
        generator, repo_root = generator_with_data
        
        pack = generator.generate(budget_tokens=4000, focus="src")
        
        # Only src files should be in top_files
        for f in pack.top_files:
            assert f['path'].startswith("src/")
    
    def test_budget_enforcement(self, generator_with_data):
        """Should enforce token budget."""
        generator, repo_root = generator_with_data
        
        pack = generator.generate(budget_tokens=500)
        
        text = pack.to_text()
        tokens = estimate_tokens(text, is_code=True)
        
        # Should be close to but not over budget
        assert tokens <= 600  # Allow some margin
    
    def test_to_text_format(self, generator_with_data):
        """to_text should produce well-formatted output."""
        generator, repo_root = generator_with_data
        
        pack = generator.generate(budget_tokens=4000)
        text = pack.to_text()
        
        assert text.startswith("# Repository Overview")
        assert "## Directory Structure" in text
        assert "## Top Files" in text
        assert "## Key Symbols" in text


class TestZoomPackGenerator:
    """Tests for ZoomPack generator."""
    
    @pytest.fixture
    def generator_with_data(self):
        """Create generator with code to zoom into."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            
            # Create actual Python file
            src_dir = repo_root / "src"
            src_dir.mkdir()
            
            code = '''"""Example module."""

def helper():
    """A helper function."""
    return 42

def main():
    """Main function."""
    result = helper()
    print(result)
    return result

class MyClass:
    """A sample class."""
    
    def method(self):
        return helper()
'''
            (src_dir / "main.py").write_text(code)
            
            # Setup database
            db_path = repo_root / ".pui" / "index.sqlite"
            db_path.parent.mkdir(parents=True)
            
            db = Database(db_path)
            db.connect()
            
            file_id = db.add_file("src/main.py", 1, len(code), "hash1")
            
            helper_id = db.add_symbol(file_id, "helper", "function", 3, 5,
                                     signature="def helper()",
                                     docstring="A helper function.")
            main_id = db.add_symbol(file_id, "main", "function", 7, 11,
                                   signature="def main()",
                                   docstring="Main function.")
            class_id = db.add_symbol(file_id, "MyClass", "class", 13, 18,
                                    signature="class MyClass:",
                                    docstring="A sample class.")
            method_id = db.add_symbol(file_id, "method", "method", 16, 17,
                                     signature="def method(self)")
            
            # Add call edges
            db.add_edge(main_id, helper_id, "call", file_id, metadata={"confidence": 0.9})
            db.add_edge(method_id, helper_id, "call", file_id, metadata={"confidence": 0.8})
            
            db.commit()
            
            generator = ZoomPackGenerator(repo_root, db)
            
            yield generator, repo_root, {
                'helper': helper_id,
                'main': main_id,
                'class': class_id,
                'method': method_id
            }
            
            db.close()
    
    def test_generate_by_symbol_id(self, generator_with_data):
        """Should generate pack by symbol ID."""
        generator, repo_root, ids = generator_with_data
        
        pack = generator.generate(str(ids['helper']), budget_tokens=4000)
        
        assert pack is not None
        assert pack.target_symbol['name'] == 'helper'
    
    def test_generate_by_symbol_name(self, generator_with_data):
        """Should generate pack by symbol name."""
        generator, repo_root, ids = generator_with_data
        
        pack = generator.generate("main", budget_tokens=4000)
        
        assert pack is not None
        assert pack.target_symbol['name'] == 'main'
    
    def test_generate_by_file_line(self, generator_with_data):
        """Should generate pack by file:line format."""
        generator, repo_root, ids = generator_with_data
        
        pack = generator.generate("src/main.py:8", budget_tokens=4000)
        
        assert pack is not None
        # Line 8 is inside main function
        assert pack.target_symbol['name'] == 'main'
    
    def test_code_slice_loaded(self, generator_with_data):
        """Should load code slice for symbol."""
        generator, repo_root, ids = generator_with_data
        
        pack = generator.generate("helper", budget_tokens=4000)
        
        assert "def helper():" in pack.code_slice
        assert "return 42" in pack.code_slice
    
    def test_callers_included(self, generator_with_data):
        """Should include callers in pack."""
        generator, repo_root, ids = generator_with_data
        
        pack = generator.generate("helper", budget_tokens=4000)
        
        assert len(pack.callers) >= 2
        caller_names = {c['name'] for c in pack.callers}
        assert 'main' in caller_names
    
    def test_callees_included(self, generator_with_data):
        """Should include callees in pack."""
        generator, repo_root, ids = generator_with_data
        
        pack = generator.generate("main", budget_tokens=4000)
        
        assert len(pack.callees) >= 1
        callee_names = {c['name'] for c in pack.callees}
        assert 'helper' in callee_names
    
    def test_docstring_included(self, generator_with_data):
        """Should include docstring when available."""
        generator, repo_root, ids = generator_with_data
        
        pack = generator.generate("helper", budget_tokens=4000)
        
        assert pack.docstring is not None
        assert "helper function" in pack.docstring
    
    def test_not_found_returns_none(self, generator_with_data):
        """Should return None for unknown symbol."""
        generator, repo_root, ids = generator_with_data
        
        pack = generator.generate("nonexistent_symbol", budget_tokens=4000)
        
        assert pack is None
    
    def test_budget_enforcement(self, generator_with_data):
        """Should enforce token budget."""
        generator, repo_root, ids = generator_with_data
        
        pack = generator.generate("main", budget_tokens=500)
        
        text = pack.to_text()
        tokens = estimate_tokens(text, is_code=True)
        
        assert tokens <= 600  # Allow some margin
    
    def test_to_text_format(self, generator_with_data):
        """to_text should produce well-formatted output."""
        generator, repo_root, ids = generator_with_data
        
        pack = generator.generate("helper", budget_tokens=4000)
        text = pack.to_text()
        
        assert text.startswith("# Zoom:")
        assert "## Signature" in text
        assert "## Documentation" in text
        assert "## Code" in text
        assert "## Callers" in text


class TestImpactPackGenerator:
    """Tests for ImpactPack generator."""
    
    @pytest.fixture
    def generator_with_data(self):
        """Create generator with dependency graph."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            db_path = repo_root / ".pui" / "index.sqlite"
            db_path.parent.mkdir(parents=True)
            
            db = Database(db_path)
            db.connect()
            
            # Create files
            main_file = db.add_file("src/main.py", 1, 100, "hash1")
            util_file = db.add_file("src/utils.py", 2, 100, "hash2")
            test_file = db.add_file("tests/test_main.py", 3, 100, "hash3")
            other_file = db.add_file("src/other.py", 4, 100, "hash4")
            
            # Create symbols
            main_id = db.add_symbol(main_file, "main", "function", 1, 10)
            helper_id = db.add_symbol(util_file, "helper", "function", 1, 10)
            utils_id = db.add_symbol(util_file, "utils_func", "function", 15, 25)
            test_id = db.add_symbol(test_file, "test_main", "function", 1, 20)
            other_id = db.add_symbol(other_file, "other_func", "function", 1, 10)
            
            # Dependencies:
            # main -> helper, main -> utils_func
            # test -> main
            # other -> helper
            db.add_edge(main_id, helper_id, "call", main_file, metadata={"confidence": 0.9})
            db.add_edge(main_id, utils_id, "call", main_file, metadata={"confidence": 0.8})
            db.add_edge(test_id, main_id, "call", test_file, metadata={"confidence": 0.95})
            db.add_edge(other_id, helper_id, "call", other_file, metadata={"confidence": 0.7})
            
            db.commit()
            
            generator = ImpactPackGenerator(repo_root, db)
            
            yield generator, repo_root, {
                'main': main_id,
                'helper': helper_id,
                'utils': utils_id,
                'test': test_id,
                'other': other_id
            }
            
            db.close()
    
    def test_generate_basic(self, generator_with_data):
        """Should generate impact pack."""
        generator, repo_root, ids = generator_with_data
        
        pack = generator.generate("helper", depth=2, budget_tokens=4000)
        
        assert isinstance(pack, ImpactPack)
        assert pack.changed_items == ["helper"]
    
    def test_affected_symbols(self, generator_with_data):
        """Should identify affected symbols."""
        generator, repo_root, ids = generator_with_data
        
        pack = generator.generate("helper", depth=2, budget_tokens=4000)
        
        # helper is called by main and other
        affected_names = {s['name'] for s in pack.affected_symbols}
        assert 'main' in affected_names or 'other_func' in affected_names
    
    def test_affected_files(self, generator_with_data):
        """Should identify affected files."""
        generator, repo_root, ids = generator_with_data
        
        pack = generator.generate("helper", depth=2, budget_tokens=4000)
        
        assert "src/main.py" in pack.affected_files
        assert "src/utils.py" in pack.affected_files  # helper is here
    
    def test_affected_tests(self, generator_with_data):
        """Should identify affected test files."""
        generator, repo_root, ids = generator_with_data
        
        pack = generator.generate("main", depth=2, budget_tokens=4000)
        
        assert "tests/test_main.py" in pack.affected_tests
    
    def test_ranked_inspection(self, generator_with_data):
        """Should rank files for inspection."""
        generator, repo_root, ids = generator_with_data
        
        pack = generator.generate("helper", depth=2, budget_tokens=4000)
        
        assert len(pack.ranked_inspection) > 0
        
        # Should have scores
        for item in pack.ranked_inspection:
            assert 'score' in item
            assert 'path' in item
            assert 'reason' in item
    
    def test_multiple_targets(self, generator_with_data):
        """Should handle multiple targets."""
        generator, repo_root, ids = generator_with_data
        
        pack = generator.generate(["helper", "main"], depth=2, budget_tokens=4000)
        
        assert len(pack.changed_items) == 2
    
    def test_by_file_path(self, generator_with_data):
        """Should accept file paths as targets."""
        generator, repo_root, ids = generator_with_data
        
        pack = generator.generate("src/utils.py", depth=2, budget_tokens=4000)
        
        # Should include all symbols from utils.py
        assert len(pack.affected_symbols) >= 2
    
    def test_depth_control(self, generator_with_data):
        """Depth parameter should control traversal."""
        generator, repo_root, ids = generator_with_data
        
        # Depth 1: only direct impact
        pack1 = generator.generate("helper", depth=1, budget_tokens=4000)
        
        # Depth 2: should include more
        pack2 = generator.generate("helper", depth=2, budget_tokens=4000)
        
        # Deeper should have equal or more affected symbols
        assert len(pack2.affected_symbols) >= len(pack1.affected_symbols)
    
    def test_budget_enforcement(self, generator_with_data):
        """Should enforce token budget."""
        generator, repo_root, ids = generator_with_data
        
        pack = generator.generate("helper", depth=2, budget_tokens=500)
        
        text = pack.to_text()
        tokens = estimate_tokens(text, is_code=True)
        
        assert tokens <= 600  # Allow some margin
    
    def test_to_text_format(self, generator_with_data):
        """to_text should produce well-formatted output."""
        generator, repo_root, ids = generator_with_data
        
        pack = generator.generate("helper", depth=2, budget_tokens=4000)
        text = pack.to_text()
        
        assert text.startswith("# Impact Analysis")
        assert "## Changed Items" in text
        assert "## Affected Files" in text
        assert "## Affected Tests" in text
        assert "## Recommended Inspection Order" in text


class TestPackSection:
    """Tests for PackSection dataclass."""
    
    def test_section_creation(self):
        """Should create section with content."""
        section = PackSection(
            title="Test Section",
            content="This is test content.",
            priority=5
        )
        
        assert section.title == "Test Section"
        assert section.priority == 5
    
    def test_section_token_count(self):
        """Should estimate token count."""
        section = PackSection(
            title="Test",
            content="def foo():\n    pass"
        )
        
        tokens = section.token_count()
        assert tokens > 0
    
    def test_section_to_text(self):
        """Should format as text."""
        section = PackSection(
            title="Test",
            content="Content here"
        )
        
        text = section.to_text()
        assert text.startswith("## Test")
        assert "Content here" in text


class TestConvenienceFunctions:
    """Tests for standalone convenience functions."""
    
    @pytest.fixture
    def setup_repo(self):
        """Setup a test repository."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            db_path = repo_root / ".pui" / "index.sqlite"
            db_path.parent.mkdir(parents=True)
            
            db = Database(db_path)
            db.connect()
            
            # Add some data
            file_id = db.add_file("test.py", 1, 100, "hash1")
            db.add_symbol(file_id, "foo", "function", 1, 5)
            db.commit()
            db.close()
            
            yield repo_root
    
    def test_repomap_function(self, setup_repo):
        """repomap() convenience function should work."""
        import os
        old_cwd = os.getcwd()
        os.chdir(setup_repo)
        
        try:
            text = repomap(budget_tokens=4000)
            assert "# Repository Overview" in text
        finally:
            os.chdir(old_cwd)
    
    def test_zoom_function(self, setup_repo):
        """zoom() convenience function should work."""
        import os
        old_cwd = os.getcwd()
        os.chdir(setup_repo)
        
        try:
            # Create a file to zoom into
            (setup_repo / "main.py").write_text("def test():\n    pass\n")
            
            text = zoom("test", budget_tokens=4000)
            # Will either find symbol or show error
            assert isinstance(text, str)
            assert len(text) > 0
        finally:
            os.chdir(old_cwd)
    
    def test_impact_function(self, setup_repo):
        """impact() convenience function should work."""
        import os
        old_cwd = os.getcwd()
        os.chdir(setup_repo)
        
        try:
            text = impact("test.py", depth=2, budget_tokens=4000)
            assert "# Impact Analysis" in text
        finally:
            os.chdir(old_cwd)


class TestTokenBudget:
    """Tests for token budget enforcement."""
    
    def test_repo_map_truncate_reduces_files(self):
        """RepoMapPack truncation should reduce file count."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            db_path = repo_root / ".pui" / "index.sqlite"
            db_path.parent.mkdir(parents=True)
            
            db = Database(db_path)
            db.connect()
            db.begin_batch(size=1000)  # Large batch to avoid premature commits
            
            # Add many files
            for i in range(20):
                file_id = db.add_file(f"src/file{i}.py", i, 1000, f"hash{i}")
                for j in range(5):
                    db.add_symbol(file_id, f"func_{i}_{j}", "function", j*10, j*10+5)
            
            db.commit()
            
            generator = RepoMapPackGenerator(repo_root, db)
            
            # Small budget should trigger truncation
            pack = generator.generate(budget_tokens=300)
            
            # Should have fewer files
            assert len(pack.top_files) < 20
            
            db.close()
    
    def test_zoom_truncate_reduces_code(self):
        """ZoomPack truncation should reduce code size."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            src_dir = repo_root / "src"
            src_dir.mkdir()
            
            # Create large file
            lines = [f"def func_{i}():" for i in range(100)]
            lines.extend(["    pass"] * 100)
            (src_dir / "big.py").write_text('\n'.join(lines))
            
            db_path = repo_root / ".pui" / "index.sqlite"
            db_path.parent.mkdir(parents=True)
            
            db = Database(db_path)
            db.connect()
            
            file_id = db.add_file("src/big.py", 1, 10000, "hash1")
            db.add_symbol(file_id, "func_0", "function", 1, 200)
            db.commit()
            
            generator = ZoomPackGenerator(repo_root, db)
            
            pack = generator.generate("func_0", budget_tokens=300)
            
            if pack:
                # Code should be truncated
                code_lines = pack.code_slice.split('\n')
                assert len(code_lines) < 150  # Should have been truncated
            
            db.close()
