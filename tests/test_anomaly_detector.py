from anomaly_detector import OperationalSignalDetector, SlidingWindowDetector


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


def test_operational_detector_finds_error_burst():
    detector = OperationalSignalDetector(
        window_seconds=5,
        error_threshold=3,
        cooldown_seconds=10,
    )
    log = {"level": "ERROR", "component": "nova.compute.manager", "message": "VM failed"}

    assert detector.observe(log, 0) is None
    assert detector.observe(log, 1) is None
    signal = detector.observe(log, 2)

    assert signal["signal_type"] == "error_burst"
    assert signal["component"] == "nova.compute.manager"


def test_operational_detector_finds_latency_spike():
    detector = OperationalSignalDetector(
        latency_threshold_seconds=1.0,
        latency_ratio=2.0,
        cooldown_seconds=10,
    )

    for index in range(5):
        detector.observe(
            {
                "level": "INFO",
                "component": "nova.osapi_compute.wsgi.server",
                "message": "request ok",
                "latency_seconds": 0.2,
            },
            index,
        )

    signal = detector.observe(
        {
            "level": "INFO",
            "component": "nova.osapi_compute.wsgi.server",
            "message": "request slow",
            "latency_seconds": 1.5,
        },
        6,
    )

    assert signal["signal_type"] == "latency_spike"
    assert signal["severity"] == "medium"


def test_operational_detector_finds_unknown_risk_pattern():
    detector = OperationalSignalDetector(cooldown_seconds=10)

    signal = detector.observe(
        {
            "level": "INFO",
            "component": "nova.api",
            "message": "backend connection refused while contacting scheduler",
        },
        0,
    )

    assert signal["signal_type"] == "unknown_risk_pattern"


def test_operational_detector_cooldown_suppresses_same_signal():
    detector = OperationalSignalDetector(
        window_seconds=5,
        error_threshold=1,
        cooldown_seconds=10,
    )
    log = {"level": "ERROR", "component": "nova.compute.manager", "message": "failed"}

    assert detector.observe(log, 0)["signal_type"] == "error_burst"
    assert detector.observe(log, 1) is None
