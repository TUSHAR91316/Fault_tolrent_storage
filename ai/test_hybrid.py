import sys
import os

# Add parent directory to path so we can import models
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models import failure_predictor, latency_predictor, security_classifier

def test_failure_predictor():
    print("[TEST] Running FailurePredictor (Ensemble IsolationForest) tests...")
    
    # 1. Normal resource load -> should be healthy (False)
    is_anomaly_normal = failure_predictor.predict_anomaly(15.0, 45.0, 35.0, 0.04)
    print(f"Normal metrics anomaly prediction (expected False): {is_anomaly_normal}")
    assert not is_anomaly_normal, "Error: Normal metrics flagged as anomaly!"

    # 2. Critical resource load -> should be degraded (True)
    is_anomaly_critical = failure_predictor.predict_anomaly(98.0, 96.0, 95.0, 2.8)
    print(f"Critical metrics anomaly prediction (expected True): {is_anomaly_critical}")
    assert is_anomaly_critical, "Error: Critical metrics not flagged as anomaly!"
    
    print("[TEST] FailurePredictor tests passed successfully.\n")

def test_latency_predictor():
    print("[TEST] Running LatencyPredictor (Ensemble LinearRegression) tests...")
    
    # Predict latency for 5MB file
    pred_latency = latency_predictor.predict_latency(40.0, 50.0, 5.0)
    print(f"Predicted download latency for 5MB file: {pred_latency:.4f} seconds")
    assert isinstance(pred_latency, float), "Error: predicted latency must be a float!"
    assert pred_latency > 0, "Error: predicted latency must be positive!"
    
    print("[TEST] LatencyPredictor tests passed successfully.\n")

def test_content_classifier_incremental():
    print("[TEST] Running ContentClassifier (Stateless Hashing + partial_fit) tests...")
    
    # 1. Test baseline scanning
    is_bad_baseline, conf_baseline = security_classifier.scan_content("This is standard code def hello(): pass")
    print(f"Baseline clean text scan (expected False): {is_bad_baseline} (confidence: {conf_baseline:.4f})")
    assert not is_bad_baseline, "Error: Standard text flagged as malicious!"

    # 2. Test heuristic scan
    is_bad_heuristic, conf_heuristic = security_classifier.scan_content("This file has flagged_unsafe_pattern inside it")
    print(f"Heuristic bad text scan (expected True): {is_bad_heuristic} (confidence: {conf_heuristic:.4f})")
    assert is_bad_heuristic, "Error: Heuristic threat went undetected!"

    # 3. Test Incremental Learning (Pattern 2)
    # We will introduce a brand new, previously unseen pattern and train the model online to recognize it
    novel_threat = "DYNAMIC_THREAT_PATTERN_XYZ_999"
    
    # Initially, it shouldn't know it is bad (or have low confidence)
    is_bad_init, conf_init = security_classifier.scan_content(novel_threat)
    print(f"Initial scan of novel threat (expected False or low conf): {is_bad_init} (confidence: {conf_init:.4f})")
    
    # Train the classifier incrementally (label=1 means suspicious)
    print(f"[TEST] Incrementally training model on novel threat pattern...")
    success = security_classifier.learn_incremental(novel_threat, 1)
    assert success, "Error: Incremental learning step failed!"
    
    # Scan again -> it should now classify it as bad/suspicious!
    is_bad_post, conf_post = security_classifier.scan_content(novel_threat)
    print(f"Post-learning scan of novel threat (expected True): {is_bad_post} (confidence: {conf_post:.4f})")
    assert is_bad_post, "Error: Content classifier failed to learn novel threat incrementally!"
    
    print("[TEST] ContentClassifier incremental tests passed successfully.\n")

if __name__ == "__main__":
    print("====================================================")
    print("    Starting AI Hybrid Model Verification Tests     ")
    print("====================================================\n")
    try:
        test_failure_predictor()
        test_latency_predictor()
        test_content_classifier_incremental()
        print("====================================================")
        print("          ALL VERIFICATION TESTS PASSED!            ")
        print("====================================================")
    except AssertionError as e:
        print(f"\n[FAIL] Test Assertion Failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Unexpected error occurred during tests: {e}")
        sys.exit(1)
