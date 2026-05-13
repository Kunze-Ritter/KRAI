"""
Tests for statistics quantiles and page coverage.

Tests advanced statistics features:
- Confidence quantiles (P50, P90, P99)
- Page coverage ratio
"""


def _quantiles(values: list[float]) -> dict[str, float]:
    """Calculate quantiles (copied from document_processor for testing)"""
    if not values:
        return {"p50": 0.0, "p90": 0.0, "p99": 0.0}
    sorted_vals = sorted(values)

    def pick(percent: float) -> float:
        if len(sorted_vals) == 1:
            return sorted_vals[0]
        idx = int(round((len(sorted_vals) - 1) * percent))
        return sorted_vals[idx]

    return {
        "p50": round(pick(0.50), 2),
        "p90": round(pick(0.90), 2),
        "p99": round(pick(0.99), 2),
    }


class TestQuantiles:
    """Test quantile calculations"""

    def test_empty_list(self):
        """Test quantiles with empty list"""
        result = _quantiles([])
        assert result == {"p50": 0.0, "p90": 0.0, "p99": 0.0}

    def test_single_value(self):
        """Test quantiles with single value"""
        result = _quantiles([0.85])
        assert result == {"p50": 0.85, "p90": 0.85, "p99": 0.85}

    def test_uniform_distribution(self):
        """Test quantiles with uniform distribution"""
        # 0.0, 0.1, 0.2, ..., 1.0 (11 values)
        values = [i / 10 for i in range(11)]
        result = _quantiles(values)

        # P50 should be around 0.5
        assert 0.4 <= result["p50"] <= 0.6
        # P90 should be around 0.9
        assert 0.8 <= result["p90"] <= 1.0
        # P99 should be around 1.0
        assert 0.9 <= result["p99"] <= 1.0

    def test_confidence_scores(self):
        """Test with realistic confidence scores"""
        # Simulate error code confidences
        confidences = [0.95, 0.92, 0.88, 0.85, 0.82, 0.78, 0.75, 0.70, 0.65, 0.60]
        result = _quantiles(confidences)

        # Verify reasonable quantiles
        assert result["p50"] > 0.7  # Median should be high
        assert result["p90"] > 0.85  # 90th percentile should be very high
        assert result["p99"] >= 0.9  # 99th percentile should be highest

    def test_sorted_order(self):
        """Test that quantiles are in ascending order"""
        values = [0.5, 0.8, 0.3, 0.9, 0.1, 0.7, 0.4, 0.6, 0.2]
        result = _quantiles(values)

        assert result["p50"] <= result["p90"]
        assert result["p90"] <= result["p99"]


class TestPageCoverage:
    """Test page coverage calculations"""

    def test_full_coverage(self):
        """Test 100% page coverage"""
        chunk_pages = {1, 2, 3, 4, 5}
        total_pages = 5

        covered = len(chunk_pages)
        ratio = covered / total_pages if total_pages else 0.0

        assert covered == 5
        assert ratio == 1.0

    def test_partial_coverage(self):
        """Test partial page coverage"""
        chunk_pages = {1, 2, 5}  # Chunks on pages 1, 2, 5
        total_pages = 10

        covered = len(chunk_pages)
        ratio = covered / total_pages if total_pages else 0.0

        assert covered == 3
        assert ratio == 0.3

    def test_zero_coverage(self):
        """Test zero page coverage"""
        chunk_pages = set()
        total_pages = 10

        covered = len(chunk_pages)
        ratio = covered / total_pages if total_pages else 0.0

        assert covered == 0
        assert ratio == 0.0

    def test_no_pages(self):
        """Test coverage with no pages"""
        chunk_pages = set()
        total_pages = 0

        covered = len(chunk_pages)
        ratio = covered / total_pages if total_pages else 0.0

        assert covered == 0
        assert ratio == 0.0

    def test_sparse_coverage(self):
        """Test sparse page coverage (e.g., only headers)"""
        # Only first and last page have chunks
        chunk_pages = {1, 100}
        total_pages = 100

        covered = len(chunk_pages)
        ratio = covered / total_pages if total_pages else 0.0

        assert covered == 2
        assert ratio == 0.02


if __name__ == "__main__":
    # Run tests without pytest
    import sys

    print("=" * 70)
    print("Testing Quantiles")
    print("=" * 70)

    test = TestQuantiles()
    tests_run = 0
    tests_passed = 0

    for method_name in dir(test):
        if method_name.startswith("test_"):
            tests_run += 1
            try:
                method = getattr(test, method_name)
                method()
                print(f"✅ {method_name}: PASSED")
                tests_passed += 1
            except AssertionError as e:
                print(f"❌ {method_name}: FAILED - {e}")
            except Exception as e:
                print(f"❌ {method_name}: ERROR - {e}")

    print("\n" + "=" * 70)
    print("Testing Page Coverage")
    print("=" * 70)

    test2 = TestPageCoverage()
    for method_name in dir(test2):
        if method_name.startswith("test_"):
            tests_run += 1
            try:
                method = getattr(test2, method_name)
                method()
                print(f"✅ {method_name}: PASSED")
                tests_passed += 1
            except AssertionError as e:
                print(f"❌ {method_name}: FAILED - {e}")
            except Exception as e:
                print(f"❌ {method_name}: ERROR - {e}")

    print("\n" + "=" * 70)
    print(f"Results: {tests_passed}/{tests_run} tests passed")
    print("=" * 70)

    sys.exit(0 if tests_passed == tests_run else 1)
