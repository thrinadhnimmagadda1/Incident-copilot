from anomaly_detector import SlidingWindowDetector


def test_detects_threshold_inside_window():
    detector = SlidingWindowDetector(window_seconds=5, threshold=3, cooldown_seconds=10)
    assert detector.observe(0) is False
    assert detector.observe(1) is False
    assert detector.observe(2) is True


def test_old_events_expire():
    detector = SlidingWindowDetector(window_seconds=2, threshold=3, cooldown_seconds=0)
    detector.observe(0)
    detector.observe(1)
    assert detector.observe(4) is False


def test_cooldown_suppresses_duplicate_detection():
    detector = SlidingWindowDetector(window_seconds=5, threshold=2, cooldown_seconds=10)
    assert detector.observe(0) is False
    assert detector.observe(1) is True
    assert detector.observe(2) is False
    assert detector.observe(3) is False
