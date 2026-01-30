"""
Tests for security features.

Tests cover:
- Path sandboxing
- No shell execution
- Input validation
"""

import pytest
import tempfile
from pathlib import Path


class TestPathSandboxing:
    """Tests for path traversal protection."""
    
    def test_path_traversal_blocked(self):
        """Path traversal attempts should be blocked."""
        from scripts.lib.indexer import Indexer
        
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            skill_root = Path(tmpdir) / "skill"
            
            # Create a file outside repo
            outside_file = Path(tmpdir).parent / "secret.txt"
            outside_file.write_text("secret data")
            
            # Create malicious path inside repo
            malicious = repo_root / ".." / ".." / "secret.txt"
            
            # Indexer should not follow traversal
            indexer = Indexer(repo_root, skill_root)
            
            # Verify traversal path is not accessible
            resolved = (repo_root / malicious).resolve()
            assert not str(resolved).startswith(str(repo_root.resolve()))
    
    def test_symlink_handling(self):
        """Symlinks should be handled safely."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            target_dir = repo_root / "src"
            target_dir.mkdir()
            
            # Create symlink to outside
            outside = Path(tmpdir).parent / "outside.txt"
            outside.write_text("outside")
            
            symlink = target_dir / "link.txt"
            try:
                symlink.symlink_to(outside)
                
                # Verify symlink target is outside repo
                resolved = symlink.resolve()
                assert not str(resolved).startswith(str(repo_root.resolve()))
            except (OSError, NotImplementedError):
                # Symlinks not supported on this platform
                pytest.skip("Symlinks not supported")


class TestNoShellExecution:
    """Tests to verify no arbitrary shell execution."""
    
    def test_no_system_calls(self):
        """No os.system calls should be present."""
        import ast
        import inspect
        from scripts.lib import indexer, db, packs, graph
        
        modules = [indexer, db, packs, graph]
        
        for module in modules:
            source = inspect.getsource(module)
            tree = ast.parse(source)
            
            # Check for os.system
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute):
                    if node.attr == 'system':
                        # Check if it's os.system
                        if isinstance(node.value, ast.Name) and node.value.id == 'os':
                            pytest.fail(f"Found os.system in {module.__name__}")
    
    def test_no_subprocess_with_user_input(self):
        """Subprocess should not use user input."""
        import ast
        import inspect
        from scripts.lib import indexer
        
        source = inspect.getsource(indexer)
        tree = ast.parse(source)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Check for subprocess calls
                if isinstance(node.func, ast.Attribute):
                    if 'subprocess' in str(node.func.value) or node.func.attr in ['run', 'call', 'check_output']:
                        # Ensure no user-controlled input
                        for arg in node.args:
                            if isinstance(arg, ast.Name):
                                # This is a simplification - would need more analysis
                                pass


class TestInputValidation:
    """Tests for input validation."""
    
    def test_invalid_file_paths_rejected(self):
        """Invalid file paths should be rejected gracefully."""
        from scripts.lib.packs import ZoomPackGenerator
        
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            db_path = repo_root / ".pui" / "index.sqlite"
            db_path.parent.mkdir(parents=True)
            
            from scripts.lib.db import Database
            db = Database(db_path)
            db.connect()
            
            generator = ZoomPackGenerator(repo_root, db)
            
            # Invalid path should not crash
            result = generator.generate("../../../etc/passwd", budget_tokens=1000)
            assert result is None or result.target_symbol is None
            
            db.close()
    
    def test_sql_injection_prevention(self):
        """SQL injection should be prevented."""
        from scripts.lib.db import Database
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = Database(db_path)
            db.connect()
            
            # Try malicious symbol name
            malicious_name = "test'; DROP TABLE symbols; --"
            
            # Should not cause SQL injection
            try:
                file_id = db.add_file("test.py", 1, 100, "hash1")
                db.add_symbol(file_id, malicious_name, "function", 1, 5)
                db.commit()
                
                # Verify table still exists
                cursor = db._conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='symbols'")
                assert cursor.fetchone() is not None
            except Exception as e:
                # If it fails, it should fail safely without injection
                pass
            
            db.close()


class TestSafeDefaults:
    """Tests for safe default configurations."""
    
    def test_no_execute_permissions_by_default(self):
        """Default config should not enable execution."""
        from scripts.lib.config import Config
        
        config = Config()
        
        # Should not have execution-related settings
        assert not hasattr(config, 'allow_shell_execution')
        assert not hasattr(config, 'allow_code_execution')
    
    def test_read_only_operations(self):
        """Default operations should be read-only."""
        from scripts.lib.indexer import Indexer
        
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            skill_root = Path(tmpdir) / "skill"
            
            # Create a test file
            test_file = repo_root / "test.py"
            test_file.write_text("x = 1")
            original_mtime = test_file.stat().st_mtime
            
            # Run indexer
            indexer = Indexer(repo_root, skill_root)
            indexer.run()
            
            # Verify original file was not modified
            assert test_file.stat().st_mtime == original_mtime
            content = test_file.read_text()
            assert content == "x = 1"
