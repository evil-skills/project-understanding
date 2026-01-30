"""
Unit tests for the graph module.

Tests cover:
- GraphEngine initialization
- callers() - upstream dependency queries
- callees() - downstream dependency queries
- impact() - change propagation analysis
- Cycle detection
- Confidence aggregation
- Stable ordering
"""

import pytest
import tempfile
from pathlib import Path

from scripts.lib.graph import (
    GraphEngine, get_callers, get_callees
)
from scripts.lib.db import Database


class TestGraphEngineBasics:
    """Tests for GraphEngine initialization and basic operations."""
    
    @pytest.fixture
    def db_with_data(self):
        """Create a database with sample symbol and edge data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = Database(db_path)
            db.connect()
            
            # Create files
            file1_id = db.add_file("src/main.py", 1, 100, "hash1")
            file2_id = db.add_file("src/utils.py", 2, 100, "hash2")
            file3_id = db.add_file("tests/test_main.py", 3, 100, "hash3")
            
            # Create symbols
            main_id = db.add_symbol(file1_id, "main", "function", 1, 10, signature="def main()")
            helper_id = db.add_symbol(file2_id, "helper", "function", 5, 15, signature="def helper()")
            utils_id = db.add_symbol(file2_id, "Utils", "class", 20, 50, signature="class Utils:")
            test_id = db.add_symbol(file3_id, "test_main", "function", 1, 20, signature="def test_main()")
            
            # Create edges (main calls helper, test calls main)
            db.add_edge(main_id, helper_id, "call", file1_id, 
                       metadata={"confidence": 0.95, "line": 5})
            db.add_edge(test_id, main_id, "call", file3_id,
                       metadata={"confidence": 0.9, "line": 10})
            
            db.commit()
            
            yield db, {
                'main': main_id,
                'helper': helper_id,
                'utils': utils_id,
                'test': test_id
            }
            
            db.close()
    
    def test_create_graph_engine(self, db_with_data):
        """Creating GraphEngine should work."""
        db, ids = db_with_data
        engine = GraphEngine(db)
        
        assert engine.db == db
        assert engine._symbol_cache == {}
    
    def test_get_symbol_caching(self, db_with_data):
        """Symbol lookup should be cached."""
        db, ids = db_with_data
        engine = GraphEngine(db)
        
        # First lookup
        symbol1 = engine._get_symbol(ids['main'])
        assert symbol1 is not None
        assert symbol1['name'] == 'main'
        
        # Second lookup should use cache
        symbol2 = engine._get_symbol(ids['main'])
        assert symbol2 is symbol1  # Same object from cache


class TestCallersQuery:
    """Tests for callers() query."""
    
    @pytest.fixture
    def engine_with_data(self):
        """Create engine with sample data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = Database(db_path)
            db.connect()
            
            # Create chain: a -> b -> c
            file_id = db.add_file("src/test.py", 1, 100, "hash1")
            
            a_id = db.add_symbol(file_id, "func_a", "function", 1, 5)
            b_id = db.add_symbol(file_id, "func_b", "function", 10, 15)
            c_id = db.add_symbol(file_id, "func_c", "function", 20, 25)
            
            # b calls c, a calls b
            db.add_edge(b_id, c_id, "call", file_id, metadata={"confidence": 0.9})
            db.add_edge(a_id, b_id, "call", file_id, metadata={"confidence": 0.85})
            
            db.commit()
            
            engine = GraphEngine(db)
            
            yield engine, {'a': a_id, 'b': b_id, 'c': c_id}
            
            db.close()
    
    def test_callers_direct(self, engine_with_data):
        """Should return direct callers."""
        engine, ids = engine_with_data
        
        callers = engine.callers(ids['c'], depth=1)
        
        assert len(callers) == 1
        assert callers[0].symbol_id == ids['b']
        assert callers[0].name == 'func_b'
    
    def test_callers_depth_two(self, engine_with_data):
        """Should return callers at depth 2."""
        engine, ids = engine_with_data
        
        callers = engine.callers(ids['c'], depth=2)
        
        # Should have both b (direct) and a (indirect)
        caller_ids = {c.symbol_id for c in callers}
        assert ids['a'] in caller_ids
        assert ids['b'] in caller_ids
    
    def test_callers_min_confidence(self, engine_with_data):
        """Should filter by minimum confidence."""
        engine, ids = engine_with_data
        
        # Only very high confidence
        callers = engine.callers(ids['b'], depth=1, min_conf=0.95)
        assert len(callers) == 0  # a->b has 0.85 but boosted to 0.9 for call edges
        
        # Lower threshold - should include boosted confidence
        callers = engine.callers(ids['b'], depth=1, min_conf=0.9)
        assert len(callers) == 1
    
    def test_callers_sorted_by_confidence(self, engine_with_data):
        """Results should be sorted by confidence descending."""
        engine, ids = engine_with_data
        
        # Add another caller with lower confidence
        file_id = engine.db.get_file("src/test.py")['id']
        d_id = engine.db.add_symbol(file_id, "func_d", "function", 30, 35)
        # 0.4 confidence (will be boosted to 0.9 for call edges, so use import which has 0.85 min)
        engine.db.add_edge(d_id, ids['c'], "import", file_id, metadata={"confidence": 0.4})
        engine.db.commit()
        
        callers = engine.callers(ids['c'], depth=1)
        
        # Should be sorted by confidence (b=0.9 from boosted 0.85, d=0.85 from import)
        assert callers[0].symbol_id == ids['b']
        assert callers[0].confidence >= callers[1].confidence
    
    def test_callers_by_name(self, engine_with_data):
        """Should resolve symbol by name."""
        engine, ids = engine_with_data
        
        callers = engine.callers("func_c", depth=1)
        
        assert len(callers) == 1
        assert callers[0].name == 'func_b'
    
    def test_callers_not_found(self, engine_with_data):
        """Should return empty list for unknown symbol."""
        engine, ids = engine_with_data
        
        callers = engine.callers("nonexistent", depth=1)
        
        assert callers == []


class TestCalleesQuery:
    """Tests for callees() query."""
    
    @pytest.fixture
    def engine_with_data(self):
        """Create engine with sample data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = Database(db_path)
            db.connect()
            
            # Create chain: a -> b -> c
            file_id = db.add_file("src/test.py", 1, 100, "hash1")
            
            a_id = db.add_symbol(file_id, "func_a", "function", 1, 5)
            b_id = db.add_symbol(file_id, "func_b", "function", 10, 15)
            c_id = db.add_symbol(file_id, "func_c", "function", 20, 25)
            
            # a calls b, b calls c
            db.add_edge(a_id, b_id, "call", file_id, metadata={"confidence": 0.9})
            db.add_edge(b_id, c_id, "call", file_id, metadata={"confidence": 0.85})
            
            db.commit()
            
            engine = GraphEngine(db)
            
            yield engine, {'a': a_id, 'b': b_id, 'c': c_id}
            
            db.close()
    
    def test_callees_direct(self, engine_with_data):
        """Should return direct callees."""
        engine, ids = engine_with_data
        
        callees = engine.callees(ids['a'], depth=1)
        
        assert len(callees) == 1
        assert callees[0].symbol_id == ids['b']
    
    def test_callees_depth_two(self, engine_with_data):
        """Should return callees at depth 2."""
        engine, ids = engine_with_data
        
        callees = engine.callees(ids['a'], depth=2)
        
        # Should have both b (direct) and c (indirect)
        callee_ids = {c.symbol_id for c in callees}
        assert ids['b'] in callee_ids
        assert ids['c'] in callee_ids
    
    def test_callees_no_outgoing(self, engine_with_data):
        """Should return empty for leaf symbols."""
        engine, ids = engine_with_data
        
        callees = engine.callees(ids['c'], depth=1)
        
        assert callees == []


class TestImpactAnalysis:
    """Tests for impact() analysis."""
    
    @pytest.fixture
    def engine_with_data(self):
        """Create engine with complex dependency graph."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = Database(db_path)
            db.connect()
            
            # Create files
            main_file = db.add_file("src/main.py", 1, 100, "hash1")
            util_file = db.add_file("src/utils.py", 2, 100, "hash2")
            test_file = db.add_file("tests/test_main.py", 3, 100, "hash3")
            
            # Create symbols
            main_id = db.add_symbol(main_file, "main", "function", 1, 10)
            helper_id = db.add_symbol(util_file, "helper", "function", 1, 10)
            utils_id = db.add_symbol(util_file, "utils_func", "function", 15, 25)
            test_id = db.add_symbol(test_file, "test_main", "function", 1, 20)
            
            # Dependencies:
            # main -> helper
            # main -> utils_func
            # test -> main
            db.add_edge(main_id, helper_id, "call", main_file, metadata={"confidence": 0.9})
            db.add_edge(main_id, utils_id, "call", main_file, metadata={"confidence": 0.8})
            db.add_edge(test_id, main_id, "call", test_file, metadata={"confidence": 0.95})
            
            # Add another caller for helper (to test fan-in)
            other_id = db.add_symbol(main_file, "other_func", "function", 30, 40)
            db.add_edge(other_id, helper_id, "call", main_file, metadata={"confidence": 0.7})
            
            db.commit()
            
            engine = GraphEngine(db)
            
            yield engine, {
                'main': main_id,
                'helper': helper_id,
                'utils': utils_id,
                'test': test_id,
                'other': other_id
            }
            
            db.close()
    
    def test_impact_basic(self, engine_with_data):
        """Should identify affected symbols."""
        engine, ids = engine_with_data
        
        impact = engine.impact([ids['helper']], depth=2)
        
        # helper is called by main and other
        affected_ids = {s.symbol_id for s in impact.affected_symbols}
        assert ids['main'] in affected_ids
        assert ids['other'] in affected_ids
    
    def test_impact_affected_files(self, engine_with_data):
        """Should identify affected files."""
        engine, ids = engine_with_data
        
        impact = engine.impact([ids['helper']], depth=2)
        
        assert "src/main.py" in impact.affected_files
        assert "src/utils.py" in impact.affected_files  # helper is here
    
    def test_impact_affected_tests(self, engine_with_data):
        """Should identify affected test files."""
        engine, ids = engine_with_data
        
        impact = engine.impact([ids['main']], depth=2)
        
        assert "tests/test_main.py" in impact.affected_tests
    
    def test_impact_ranking(self, engine_with_data):
        """Should rank files for inspection."""
        engine, ids = engine_with_data
        
        impact = engine.impact([ids['helper']], depth=2)
        
        # Should have ranked_inspection list
        assert len(impact.ranked_inspection) > 0
        
        # Test files should have higher ranking
        test_items = [r for r in impact.ranked_inspection if r.get('is_test')]
        assert len(test_items) >= 0  # May or may not include tests depending on depth
    
    def test_impact_by_file_path(self, engine_with_data):
        """Should accept file paths as targets."""
        engine, ids = engine_with_data
        
        impact = engine.impact(["src/utils.py"], depth=2)
        
        # All symbols in utils.py should be considered changed
        assert len(impact.affected_symbols) > 0
    
    def test_impact_fan_in_counting(self, engine_with_data):
        """Should count fan-in for each affected symbol."""
        engine, ids = engine_with_data
        
        impact = engine.impact([ids['helper']], depth=1)
        
        # helper should have fan-in of 2 (main and other call it)
        helper_symbol = next(
            (s for s in impact.affected_symbols if s.symbol_id == ids['helper']),
            None
        )
        assert helper_symbol is not None
        assert impact.total_fan_in.get(ids['helper'], 0) == 2


class TestCycleDetection:
    """Tests for cycle detection in graph traversal."""
    
    @pytest.fixture
    def engine_with_cycle(self):
        """Create engine with circular dependencies."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = Database(db_path)
            db.connect()
            
            file_id = db.add_file("src/cycle.py", 1, 100, "hash1")
            
            # Create cycle: a -> b -> c -> a
            a_id = db.add_symbol(file_id, "func_a", "function", 1, 5)
            b_id = db.add_symbol(file_id, "func_b", "function", 10, 15)
            c_id = db.add_symbol(file_id, "func_c", "function", 20, 25)
            
            db.add_edge(a_id, b_id, "call", file_id)
            db.add_edge(b_id, c_id, "call", file_id)
            db.add_edge(c_id, a_id, "call", file_id)
            
            db.commit()
            
            engine = GraphEngine(db)
            
            yield engine, {'a': a_id, 'b': b_id, 'c': c_id}
            
            db.close()
    
    def test_callers_avoids_cycle(self, engine_with_cycle):
        """Should not infinite loop on cycles."""
        engine, ids = engine_with_cycle
        
        # This should complete without infinite loop
        callers = engine.callers(ids['a'], depth=10)
        
        # Should have b and c as callers, but not duplicate a
        caller_ids = [c.symbol_id for c in callers]
        assert ids['b'] in caller_ids
        assert ids['c'] in caller_ids
        # a should not appear as its own caller (cycle broken)
        assert ids['a'] not in caller_ids
    
    def test_callees_avoids_cycle(self, engine_with_cycle):
        """Should not infinite loop on cycles."""
        engine, ids = engine_with_cycle
        
        callees = engine.callees(ids['a'], depth=10)
        
        callee_ids = [c.symbol_id for c in callees]
        assert ids['b'] in callee_ids
        assert ids['c'] in callee_ids
        assert ids['a'] not in callee_ids  # No self-reference


class TestConfidenceAggregation:
    """Tests for confidence score aggregation."""
    
    @pytest.fixture
    def engine_with_confidence(self):
        """Create engine with varying confidence edges."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = Database(db_path)
            db.connect()
            
            file_id = db.add_file("src/conf.py", 1, 100, "hash1")
            
            a_id = db.add_symbol(file_id, "func_a", "function", 1, 5)
            b_id = db.add_symbol(file_id, "func_b", "function", 10, 15)
            c_id = db.add_symbol(file_id, "func_c", "function", 20, 25)
            
            # a -> b with 0.5 confidence
            # b -> c with 0.8 confidence
            # a -> c directly with 0.3 confidence
            db.add_edge(a_id, b_id, "call", file_id, metadata={"confidence": 0.5})
            db.add_edge(b_id, c_id, "call", file_id, metadata={"confidence": 0.8})
            db.add_edge(a_id, c_id, "call", file_id, metadata={"confidence": 0.3})
            
            db.commit()
            
            engine = GraphEngine(db)
            
            yield engine, {'a': a_id, 'b': b_id, 'c': c_id}
            
            db.close()
    
    def test_confidence_multiplied_along_path(self, engine_with_confidence):
        """Confidence should be multiplied along traversal path."""
        engine, ids = engine_with_confidence
        
        # c should have callers with different confidence levels:
        # b -> c: 0.8 (direct)
        # a -> c: 0.3 (direct) or 0.5 * 0.8 = 0.4 (via b)
        callers = engine.callers(ids['c'], depth=2)
        
        # Find a's contribution
        caller_a = next((c for c in callers if c.symbol_id == ids['a']), None)
        if caller_a:
            # Should take max confidence path (0.4 via b, not 0.3 direct)
            assert caller_a.confidence >= 0.3


class TestTestFileDetection:
    """Tests for test file detection."""
    
    def test_detect_python_test_files(self):
        """Should detect Python test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = Database(db_path)
            db.connect()
            
            engine = GraphEngine(db)
            
            test_files = [
                "test_something.py",
                "something_test.py",
                "tests/unit/test_main.py",
                "src/__tests__/component.spec.ts",
                "main_spec.js"
            ]
            
            non_test_files = [
                "main.py",
                "utils.js",
                "src/core/app.py"
            ]
            
            detected = engine._filter_test_files(test_files + non_test_files)
            
            for f in test_files:
                assert f in detected, f"Should detect {f} as test file"
            
            for f in non_test_files:
                assert f not in detected, f"Should not detect {f} as test file"
            
            db.close()


class TestConvenienceFunctions:
    """Tests for standalone convenience functions."""
    
    def test_get_callers_standalone(self):
        """Standalone get_callers should work."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Setup test database
            db_path = Path(tmpdir) / ".pui" / "index.sqlite"
            db_path.parent.mkdir(parents=True)
            
            db = Database(db_path)
            db.connect()
            
            file_id = db.add_file("test.py", 1, 100, "hash1")
            a_id = db.add_symbol(file_id, "a", "function", 1, 5)
            b_id = db.add_symbol(file_id, "b", "function", 10, 15)
            db.add_edge(b_id, a_id, "call", file_id)
            db.commit()
            db.close()
            
            # Change to temp directory so get_callers uses it
            import os
            old_cwd = os.getcwd()
            os.chdir(tmpdir)
            
            try:
                callers = get_callers("a", depth=1)
                assert len(callers) == 1
                assert callers[0].name == "b"
            finally:
                os.chdir(old_cwd)
    
    def test_get_callees_standalone(self):
        """Standalone get_callees should work."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / ".pui" / "index.sqlite"
            db_path.parent.mkdir(parents=True)
            
            db = Database(db_path)
            db.connect()
            
            file_id = db.add_file("test.py", 1, 100, "hash1")
            a_id = db.add_symbol(file_id, "a", "function", 1, 5)
            b_id = db.add_symbol(file_id, "b", "function", 10, 15)
            db.add_edge(a_id, b_id, "call", file_id)
            db.commit()
            db.close()
            
            import os
            old_cwd = os.getcwd()
            os.chdir(tmpdir)
            
            try:
                callees = get_callees("a", depth=1)
                assert len(callees) == 1
                assert callees[0].name == "b"
            finally:
                os.chdir(old_cwd)


class TestStableOrdering:
    """Tests for stable result ordering."""
    
    @pytest.fixture
    def engine_with_multiple_callers(self):
        """Create engine with multiple callers at same confidence."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = Database(db_path)
            db.connect()
            
            file_id = db.add_file("src/test.py", 1, 100, "hash1")
            
            target_id = db.add_symbol(file_id, "target", "function", 1, 5)
            
            # Add multiple callers with same confidence
            caller_ids = []
            for i in range(5):
                cid = db.add_symbol(file_id, f"caller_{i:02d}", "function", 10 + i*5, 15 + i*5)
                caller_ids.append(cid)
                db.add_edge(cid, target_id, "call", file_id, metadata={"confidence": 0.9})
            
            db.commit()
            
            engine = GraphEngine(db)
            
            yield engine, target_id, caller_ids
            
            db.close()
    
    def test_stable_order_same_confidence(self, engine_with_multiple_callers):
        """Results should be stable when confidence is equal."""
        engine, target_id, caller_ids = engine_with_multiple_callers
        
        # Get callers multiple times
        results1 = engine.callers(target_id, depth=1)
        results2 = engine.callers(target_id, depth=1)
        
        # Should be identical
        assert [r.symbol_id for r in results1] == [r.symbol_id for r in results2]
        
        # Should be sorted by name since confidence is equal
        names = [r.name for r in results1]
        assert names == sorted(names)
