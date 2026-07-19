import os
import time
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LinearRegression
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
import threading

# ─────────────────────────────────────────────────────────────────────────────
# 1. Predictive Node Failure Model (Isolation Forest)
# ─────────────────────────────────────────────────────────────────────────────
class FailurePredictor:
    def __init__(self):
        self.model = None

    def train_baseline(self):
        """Train on mock normal baseline telemetry metrics."""
        np.random.seed(42)
        normal_cpu     = np.random.uniform(5.0, 60.0, 1000)
        normal_ram     = np.random.uniform(20.0, 70.0, 1000)
        normal_disk    = np.random.uniform(10.0, 80.0, 1000)
        normal_latency = np.random.uniform(0.01, 0.2, 1000)
        data = np.column_stack((normal_cpu, normal_ram, normal_disk, normal_latency))
        self.model = IsolationForest(contamination=0.02, random_state=42)
        self.model.fit(data)

    def predict_anomaly(self, cpu, ram, disk, latency):
        """Returns True if metrics are anomalous (predicting failure), False if normal."""
        # FIX Bug 4: use 'is None' instead of falsy check — a fitted sklearn model
        #            is always truthy, so 'if not self.model' never triggers retraining.
        if self.model is None:
            self.train_baseline()
        features = np.array([[cpu, ram, disk, latency]])
        pred = self.model.predict(features)
        return pred[0] == -1

# ─────────────────────────────────────────────────────────────────────────────
# 2. Intelligent Load Balancing Model (Regression)
# ─────────────────────────────────────────────────────────────────────────────
class LatencyPredictor:
    def __init__(self):
        self.model = None

    def train_baseline(self):
        """Train on mock latency data to predict response times based on load and file size."""
        np.random.seed(42)
        cpu       = np.random.uniform(5.0, 95.0, 1000)
        ram       = np.random.uniform(10.0, 90.0, 1000)
        file_size = np.random.uniform(0.1, 100.0, 1000)
        noise     = np.random.normal(0, 0.02, 1000)
        latency   = 0.05 + (cpu * 0.001) + (ram * 0.0005) + (file_size * 0.003) + noise
        latency   = np.clip(latency, 0.01, 2.0)
        X = np.column_stack((cpu, ram, file_size))
        self.model = LinearRegression()
        self.model.fit(X, latency)

    def predict_latency(self, cpu, ram, file_size_mb):
        """Predicts download latency in seconds."""
        # FIX Bug 4 (same pattern): use 'is None' so fallback training actually fires.
        if self.model is None:
            self.train_baseline()
        features = np.array([[cpu, ram, file_size_mb]])
        return float(self.model.predict(features)[0])

# ─────────────────────────────────────────────────────────────────────────────
# 3. Content Security Classifier (TF-IDF + Naive Bayes Classifier)
# ─────────────────────────────────────────────────────────────────────────────
class ContentClassifier:
    def __init__(self):
        self.vectorizer = None
        self.classifier = None

    def train_baseline(self):
        """Train a lightweight text classifier using generic representations."""
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
        self.vectorizer = TfidfVectorizer(
            lowercase=True, min_df=1, analyzer='char_wb', ngram_range=(2, 4)
        )
        X = self.vectorizer.fit_transform(texts)
        self.classifier = MultinomialNB()
        self.classifier.fit(X, labels)

    def scan_content(self, file_content_str):
        """Scans text-based file contents. Returns (is_suspicious, confidence)."""
        if self.classifier is None:
            self.train_baseline()
        try:
            lower_content = file_content_str.lower()
            heuristics = ["suspicious_pattern_type", "flagged_unsafe_pattern"]
            for h in heuristics:
                if h in lower_content:
                    return True, 1.0
            vec  = self.vectorizer.transform([file_content_str])
            pred = self.classifier.predict(vec)[0]
            probs = self.classifier.predict_proba(vec)[0]
            return bool(pred == 1), float(probs[1])
        except Exception:
            return False, 0.0

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
failure_predictor     = FailurePredictor();   failure_predictor.train_baseline()
latency_predictor     = LatencyPredictor();   latency_predictor.train_baseline()
security_classifier   = ContentClassifier();  security_classifier.train_baseline()
access_anomaly_detector = AccessAnomalyDetector()

if __name__ == "__main__":
    print("Testing models...")
    print("Anomaly prediction (normal):", failure_predictor.predict_anomaly(10, 30, 40, 0.05))
    print("Anomaly prediction (critical):", failure_predictor.predict_anomaly(99, 95, 95, 2.5))
    print("Predicted download latency:", latency_predictor.predict_latency(50, 40, 10.5), "sec")
    print("Suspicious scan result:", security_classifier.scan_content("SUSPICIOUS_PATTERN_TYPE_X_PAYLOAD"))
    print("Clean code scan result:", security_classifier.scan_content("def add(a,b): return a+b"))
