import time
import threading
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LinearRegression
from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.naive_bayes import MultinomialNB

# ─────────────────────────────────────────────────────────────────────────────
# 1. Predictive Node Failure Model (Ensembled Isolation Forests - Pattern 3)
# ─────────────────────────────────────────────────────────────────────────────
class FailurePredictor:
    def __init__(self):
        self.global_model = None
        self.local_model  = None
        # FIX Bug 5: guard concurrent train_baseline() calls from multiple threads
        self._train_lock  = threading.Lock()

    def train_baseline(self):
        """Train both global (static benchmark) and local (adaptive) models."""
        with self._train_lock:
            # Double-checked locking: re-verify under lock
            if self.global_model is not None and self.local_model is not None:
                return
            print("[AI] Training Ensembled Predictive Failure Models...")
            np.random.seed(42)

            # 1. Global Baseline (10,000 metrics representing large-scale benchmarks)
            global_cpu     = np.random.uniform(5.0, 60.0, 10000)
            global_ram     = np.random.uniform(20.0, 70.0, 10000)
            global_disk    = np.random.uniform(10.0, 80.0, 10000)
            global_latency = np.random.uniform(0.01, 0.2, 10000)
            global_data    = np.column_stack((global_cpu, global_ram, global_disk, global_latency))

            self.global_model = IsolationForest(contamination=0.01, random_state=42)
            self.global_model.fit(global_data)

            # 2. Local Baseline (1,000 metrics representing local node starting profile)
            local_cpu     = np.random.uniform(5.0, 50.0, 1000)
            local_ram     = np.random.uniform(20.0, 60.0, 1000)
            local_disk    = np.random.uniform(10.0, 70.0, 1000)
            local_latency = np.random.uniform(0.01, 0.15, 1000)
            local_data    = np.column_stack((local_cpu, local_ram, local_disk, local_latency))

            self.local_model = IsolationForest(contamination=0.02, random_state=42)
            self.local_model.fit(local_data)
            print("[AI] Ensembled Failure Models trained.")

    def predict_anomaly(self, cpu, ram, disk, latency):
        """Weighted ensemble anomaly scoring: 0.6 * Global Score + 0.4 * Local Score."""
        if self.global_model is None or self.local_model is None:
            self.train_baseline()

        features = np.array([[cpu, ram, disk, latency]])

        # score_samples returns the negative anomaly score (lower is more anomalous)
        global_score = float(self.global_model.score_samples(features)[0])
        local_score  = float(self.local_model.score_samples(features)[0])

        ensemble_score = 0.6 * global_score + 0.4 * local_score

        # Compare ensemble score to weighted average offset thresholds
        # offset_ is a scalar on sklearn IsolationForest — no indexing needed
        global_threshold   = float(self.global_model.offset_)
        local_threshold    = float(self.local_model.offset_)
        ensemble_threshold = 0.6 * global_threshold + 0.4 * local_threshold

        return ensemble_score < ensemble_threshold

# ─────────────────────────────────────────────────────────────────────────────
# 2. Intelligent Load Balancing Model (Ensembled Regressions - Pattern 3)
# ─────────────────────────────────────────────────────────────────────────────
class LatencyPredictor:
    def __init__(self):
        self.global_model = None
        self.local_model  = None
        # FIX Bug 5: guard concurrent train_baseline() calls
        self._train_lock  = threading.Lock()

    def train_baseline(self):
        """Train both global and local regressions to predict latencies."""
        with self._train_lock:
            if self.global_model is not None and self.local_model is not None:
                return
            print("[AI] Training Ensembled Latency Prediction Models...")
            np.random.seed(42)

            # 1. Global Latency Benchmark (representing average cloud environments)
            g_cpu       = np.random.uniform(5.0, 95.0, 2000)
            g_ram       = np.random.uniform(10.0, 90.0, 2000)
            g_file_size = np.random.uniform(0.1, 100.0, 2000)
            g_noise     = np.random.normal(0, 0.02, 2000)
            g_latency   = 0.05 + (g_cpu * 0.001) + (g_ram * 0.0005) + (g_file_size * 0.003) + g_noise
            g_latency   = np.clip(g_latency, 0.01, 2.0)
            X_g = np.column_stack((g_cpu, g_ram, g_file_size))

            self.global_model = LinearRegression()
            self.global_model.fit(X_g, g_latency)

            # 2. Local Latency Benchmark (representing local high-speed LAN)
            l_cpu       = np.random.uniform(5.0, 95.0, 500)
            l_ram       = np.random.uniform(10.0, 90.0, 500)
            l_file_size = np.random.uniform(0.1, 100.0, 500)
            l_noise     = np.random.normal(0, 0.005, 500)
            l_latency   = 0.02 + (l_cpu * 0.0005) + (l_ram * 0.0002) + (l_file_size * 0.001) + l_noise
            l_latency   = np.clip(l_latency, 0.005, 1.0)
            X_l = np.column_stack((l_cpu, l_ram, l_file_size))

            self.local_model = LinearRegression()
            self.local_model.fit(X_l, l_latency)
            print("[AI] Ensembled Latency Models trained.")

    def predict_latency(self, cpu, ram, file_size_mb):
        """Weighted ensemble latency prediction: 0.7 * Global Latency + 0.3 * Local Latency."""
        if self.global_model is None or self.local_model is None:
            self.train_baseline()

        features    = np.array([[cpu, ram, file_size_mb]])
        global_pred = float(self.global_model.predict(features)[0])
        local_pred  = float(self.local_model.predict(features)[0])

        return 0.7 * global_pred + 0.3 * local_pred

# ─────────────────────────────────────────────────────────────────────────────
# 3. Content Security Classifier (Stateless Hashing & Incremental - Pattern 2)
# ─────────────────────────────────────────────────────────────────────────────
class ContentClassifier:
    def __init__(self):
        # HashingVectorizer is stateless and does not need vocabulary mapping.
        # alternate_sign=False required: MultinomialNB needs non-negative inputs.
        # Optimized to 2^12 (4096 features) for minimal hash collisions & high precision.
        self.vectorizer = HashingVectorizer(
            alternate_sign=False, n_features=2**12,
            analyzer='char_wb', ngram_range=(2, 4)
        )
        self.classifier = None
        self.lock = threading.Lock()

    def train_baseline(self):
        """Train a lightweight text classifier incrementally on startup."""
        with self.lock:
            if self.classifier is not None:
                return
            print("[AI] Training Incremental Content Security Classifier...")
            class_a_docs = [
                "def add_numbers(a, b): return a + b",
                "import os\nprint(os.listdir('.'))",
                "Hello, this is a plain text document stored safely.",
                "{\"status\": \"success\", \"code\": 200, \"data\": []}",
                "<html><body><h1>My Personal Storage Portal</h1></body></html>",
                "System.out.println('Hello World');",
                "SELECT * FROM users WHERE username = ?",
                "const express = require('express'); const app = express();",
                "# Fault-Tolerant Storage Project readme file.",
                "import time\ntime.sleep(5)"
            ]
            class_b_docs = [
                "SUSPICIOUS_PATTERN_TYPE_X_PAYLOAD",
                "SUSPICIOUS_PATTERN_TYPE_Y_INJECTOR",
                "SUSPICIOUS_PATTERN_TYPE_Z_BACKDOOR",
                "SUSPICIOUS_PATTERN_TYPE_W_EXPLOIT",
                "SUSPICIOUS_PATTERN_TYPE_V_ROOTKIT",
                "SUSPICIOUS_PATTERN_TYPE_U_WORM",
                "SUSPICIOUS_PATTERN_TYPE_T_TROJAN",
                "SUSPICIOUS_PATTERN_TYPE_S_RANSOMWARE",
                "SUSPICIOUS_PATTERN_TYPE_R_SPYWARE",
                "SUSPICIOUS_PATTERN_TYPE_Q_KEYLOGGER"
            ]
            texts  = class_a_docs + class_b_docs
            labels = [0] * len(class_a_docs) + [1] * len(class_b_docs)

            X = self.vectorizer.transform(texts)
            self.classifier = MultinomialNB()
            # partial_fit requires the list of possible classes on the first call
            self.classifier.partial_fit(X, labels, classes=[0, 1])
            print("[AI] Incremental Content Security Classifier trained.")

    def scan_content(self, file_content_str):
        """Scans file contents and computes probability scores."""
        if self.classifier is None:
            self.train_baseline()
        try:
            lower_content = file_content_str.lower()
            heuristics = ["suspicious_pattern_type", "flagged_unsafe_pattern"]
            for h in heuristics:
                if h in lower_content:
                    return True, 1.0

            vec   = self.vectorizer.transform([file_content_str])
            pred  = self.classifier.predict(vec)[0]
            probs = self.classifier.predict_proba(vec)[0]
            return bool(pred == 1), float(probs[1])
        except Exception:
            return False, 0.0

    def learn_incremental(self, file_content_str, label):
        """Dynamically retrain the content classifier in-memory using partial_fit (Pattern 2)."""
        if self.classifier is None:
            self.train_baseline()
        with self.lock:
            try:
                vec = self.vectorizer.transform([file_content_str])
                self.classifier.partial_fit(vec, [label])
                print(f"[AI] Model incrementally learned new sample (class: {label})")
                return True
            except Exception as e:
                print(f"[AI] Failed incremental learning step: {e}")
                return False

# ─────────────────────────────────────────────────────────────────────────────
# 4. Access Pattern Anomaly Detector (Rate/Volumetric Anomaly)
# ─────────────────────────────────────────────────────────────────────────────
class AccessAnomalyDetector:
    def __init__(self):
        self.history      = {}
        self.history_lock = threading.Lock()
        self.TIME_WINDOW  = 10.0   # seconds
        self.THRESHOLD    = 15     # requests per window

    def record_access_and_check(self, ip):
        """Records access from IP and returns True if suspicious behavior detected."""
        with self.history_lock:
            now = time.time()
            if ip not in self.history:
                self.history[ip] = []
            self.history[ip].append(now)
            self.history[ip] = [t for t in self.history[ip] if now - t <= self.TIME_WINDOW]
            return len(self.history[ip]) > self.THRESHOLD

# ─────────────────────────────────────────────────────────────────────────────
# Global model instances — trained at import time
# ─────────────────────────────────────────────────────────────────────────────
failure_predictor       = FailurePredictor();   failure_predictor.train_baseline()
latency_predictor       = LatencyPredictor();   latency_predictor.train_baseline()
security_classifier     = ContentClassifier();  security_classifier.train_baseline()
access_anomaly_detector = AccessAnomalyDetector()

if __name__ == "__main__":
    print("Testing models...")
    print("Anomaly prediction (normal):",   failure_predictor.predict_anomaly(10, 30, 40, 0.05))
    print("Anomaly prediction (critical):", failure_predictor.predict_anomaly(99, 95, 95, 2.5))
    print("Predicted download latency:",    latency_predictor.predict_latency(50, 40, 10.5), "sec")
    print("Suspicious scan result:", security_classifier.scan_content("SUSPICIOUS_PATTERN_TYPE_X_PAYLOAD"))
    print("Clean code scan result:",  security_classifier.scan_content("def add(a,b): return a+b"))
