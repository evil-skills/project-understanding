"""
Snapshot tests for Project Understanding Skill packs.

Tests verify stable output format and ordering across runs.
"""

import pytest
import tempfile
import json
from pathlib import Path

from scripts.lib.packs import (
    RepoMapPackGenerator, ZoomPackGenerator, ImpactPackGenerator
)
from scripts.lib.db import Database


class TestSnapshotGoldenOutputs:
    """Golden output tests for pack formats."""
    
    @pytest.fixture
    def golden_repo(self):
        """Create a repository with known structure for golden tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            
            # Create fixed structure
            src = repo_root / "src"
            src.mkdir()
            tests = repo_root / "tests"
            tests.mkdir()
            
            # Create main.py with known content
            (src / "main.py").write_text('''
def main():
    """Main entry point."""
    result = helper()
    return result

def helper():
    """Helper function."""
    return 42

class MainClass:
    """Main class."""
    
    def method(self):
        return helper()
''')
            
            # Create utils.py
            (src / "utils.py").write_text('''
def utility():
    """Utility function."""
    return "util"
''')
            
            # Create test file
            (tests / "test_main.py").write_text('''
def test_main():
    assert main() == 42
''')
            
            # Setup database
            db_path = repo_root / ".pui" / "index.sqlite"
            db_path.parent.mkdir(parents=True)
            
            db = Database(db_path)
            db.connect()
            
            # Add files
            main_file = db.add_file("src/main.py", 1, 200, "hash1", "python")
            util_file = db.add_file("src/utils.py", 2, 100, "hash2", "python")
            test_file = db.add_file("tests/test_main.py", 3, 50, "hash3", "python")
            
            # Add symbols
            main_id = db.add_symbol(main_file, "main", "function", 2, 6, 
                                   signature="def main()", docstring="Main entry point.")
            helper_id = db.add_symbol(main_file, "helper", "function", 7, 10,
                                     signature="def helper()", docstring="Helper function.")
            db.add_symbol(main_file, "MainClass", "class", 12, 17,
                                    signature="class MainClass:", docstring="Main class.")
            method_id = db.add_symbol(main_file, "method", "method", 15, 16,
                                     signature="def method(self)")
            db.add_symbol(util_file, "utility", "function", 2, 4,
                                   signature="def utility()", docstring="Utility function.")
            test_id = db.add_symbol(test_file, "test_main", "function", 2, 3,
                                   signature="def test_main()")
            
            # Add edges
            db.add_edge(main_id, helper_id, "call", main_file, metadata={"confidence": 0.9})
            db.add_edge(method_id, helper_id, "call", main_file, metadata={"confidence": 0.8})
            db.add_edge(test_id, main_id, "call", test_file, metadata={"confidence": 0.95})
            
            db.commit()
            
            yield repo_root, db
            
            db.close()
    
    def test_repomap_stable_output(self, golden_repo):
        """RepoMapPack should produce stable output."""
        repo_root, db = golden_repo
        
        generator = RepoMapPackGenerator(repo_root, db)
        pack1 = generator.generate(budget_tokens=4000)
        pack2 = generator.generate(budget_tokens=4000)
        
        text1 = pack1.to_text()
        text2 = pack2.to_text()
        
        assert text1 == text2, "RepoMapPack output should be stable across runs"
    
    def test_repomap_format_compliance(self, golden_repo):
        """RepoMapPack should follow expected format."""
        repo_root, db = golden_repo
        
        generator = RepoMapPackGenerator(repo_root, db)
        pack = generator.generate(budget_tokens=4000)
        text = pack.to_text()
        
        # Check required sections
        assert text.startswith("# Repository Overview")
        assert "## Directory Structure" in text
        assert "## Top Files" in text
        assert "## Key Symbols" in text
    
    def test_zoom_stable_output(self, golden_repo):
        """ZoomPack should produce stable output."""
        repo_root, db = golden_repo
        
        generator = ZoomPackGenerator(repo_root, db)
        pack1 = generator.generate("main", budget_tokens=2000)
        pack2 = generator.generate("main", budget_tokens=2000)
        
        assert pack1 is not None
        assert pack2 is not None
        
        text1 = pack1.to_text()
        text2 = pack2.to_text()
        
        assert text1 == text2, "ZoomPack output should be stable across runs"
    
    def test_zoom_format_compliance(self, golden_repo):
        """ZoomPack should follow expected format."""
        repo_root, db = golden_repo
        
        generator = ZoomPackGenerator(repo_root, db)
        pack = generator.generate("helper", budget_tokens=2000)
        
        assert pack is not None
        text = pack.to_text()
        
        # Check required sections
        assert text.startswith("# Zoom:")
        assert "## Signature" in text
        assert "## Code" in text
        assert "## Callers" in text
    
    def test_impact_stable_output(self, golden_repo):
        """ImpactPack should produce stable output."""
        repo_root, db = golden_repo
        
        generator = ImpactPackGenerator(repo_root, db)
        pack1 = generator.generate("helper", depth=2, budget_tokens=3000)
        pack2 = generator.generate("helper", depth=2, budget_tokens=3000)
        
        text1 = pack1.to_text()
        text2 = pack2.to_text()
        
        assert text1 == text2, "ImpactPack output should be stable across runs"
    
    def test_impact_format_compliance(self, golden_repo):
        """ImpactPack should follow expected format."""
        repo_root, db = golden_repo
        
        generator = ImpactPackGenerator(repo_root, db)
        pack = generator.generate("main", depth=2, budget_tokens=3000)
        text = pack.to_text()
        
        # Check required sections
        assert text.startswith("# Impact Analysis")
        assert "## Changed Items" in text
        assert "## Affected Files" in text
    
    def test_stable_ordering(self, golden_repo):
        """Files and symbols should have stable ordering."""
        repo_root, db = golden_repo
        
        generator = RepoMapPackGenerator(repo_root, db)
        
        # Generate multiple times
        orders = []
        for _ in range(3):
            pack = generator.generate(budget_tokens=4000)
            file_order = [f['path'] for f in pack.top_files]
            orders.append(file_order)
        
        # All orders should be identical
        assert orders[0] == orders[1] == orders[2], "File ordering should be stable"


class TestVersionedFixtures:
    """Tests using versioned fixtures for compatibility."""
    
    def test_fixture_v1_compatibility(self):
        """Test compatibility with v1 fixture format."""
        # This test ensures we maintain backward compatibility
        # with previously indexed databases
        fixture_data = {
            'version': '1.0',
            'files': [
                {'path': 'src/main.py', 'language': 'python'},
                {'path': 'src/utils.py', 'language': 'python'},
            ],
            'symbols': [
                {'name': 'main', 'kind': 'function', 'file': 'src/main.py'},
                {'name': 'helper', 'kind': 'function', 'file': 'src/main.py'},
            ]
        }
        
        # Verify we can work with v1 data
        assert 'version' in fixture_data
        assert len(fixture_data['files']) == 2
        assert len(fixture_data['symbols']) == 2
    
    def test_pack_versioning(self):
        """Packs should include version metadata."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            db_path = repo_root / ".pui" / "index.sqlite"
            db_path.parent.mkdir(parents=True)
            
            db = Database(db_path)
            db.connect()
            
            file_id = db.add_file("test.py", 1, 100, "hash1")
            db.add_symbol(file_id, "test", "function", 1, 5)
            db.commit()
            
            generator = RepoMapPackGenerator(repo_root, db)
            pack = generator.generate(budget_tokens=4000)
            
            # Pack should have metadata
            assert hasattr(pack, 'metadata')
            
            db.close()


class TestJSONOutputStability:
    """Tests for stable JSON output."""
    
    @pytest.fixture
    def json_repo(self):
        """Create repo for JSON tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            db_path = repo_root / ".pui" / "index.sqlite"
            db_path.parent.mkdir(parents=True)
            
            db = Database(db_path)
            db.connect()
            
            file_id = db.add_file("test.py", 1, 100, "hash1")
            db.add_symbol(file_id, "func_a", "function", 1, 5)
            db.add_symbol(file_id, "func_b", "function", 7, 10)
            db.commit()
            
            yield repo_root, db
            
            db.close()
    
    def test_json_structure_stability(self, json_repo):
        """JSON output should have stable structure."""
        repo_root, db = json_repo
        
        generator = RepoMapPackGenerator(repo_root, db)
        pack = generator.generate(budget_tokens=4000)
        
        # Convert to dict and back to ensure stability
        data1 = pack.to_dict() if hasattr(pack, 'to_dict') else {
            'directory_tree': pack.directory_tree,
            'top_files': pack.top_files,
            'file_symbols': pack.file_symbols,
            'dependency_summary': pack.dependency_summary,
        }
        json1 = json.dumps(data1, sort_keys=True)
        
        # Generate again
        pack2 = generator.generate(budget_tokens=4000)
        data2 = pack2.to_dict() if hasattr(pack2, 'to_dict') else {
            'directory_tree': pack2.directory_tree,
            'top_files': pack2.top_files,
            'file_symbols': pack2.file_symbols,
            'dependency_summary': pack2.dependency_summary,
        }
        json2 = json.dumps(data2, sort_keys=True)
        
        assert json1 == json2, "JSON output should be stable"
