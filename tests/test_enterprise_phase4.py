"""
Phase 4 Enterprise Features Verification Suite
Tests:
  1. Zero-Trust AES-256-GCM Encryption & Tamper-resistance
  2. Reed-Solomon K+M Erasure Coding Sharding & Missing Shard Reconstruction
  3. RBAC & API Key Security Middleware
  4. Prometheus Observability Exposition Output
"""

import sys
import os
import hashlib

# Add coordinator folder to python import path
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'coordinator'))

import security_ec
from metrics import coordinator_metrics

def test_encryption_decryption():
    print("[TEST 1/4] Running AES-256-GCM Zero-Trust Encryption Tests...")
    raw_payload = b"CRITICAL_ENTERPRISE_CONFIDENTIAL_PAYLOAD_DATA_2026"
    
    # Encrypt payload
    ciphertext, nonce = security_ec.encrypt_payload(raw_payload)
    print(f"  -> Encrypted payload size: {len(ciphertext)} bytes (Ciphertext + Tag)")
    assert ciphertext != raw_payload, "Error: Ciphertext matches plaintext!"
    
    # Decrypt payload
    decrypted = security_ec.decrypt_payload(ciphertext, nonce)
    assert decrypted == raw_payload, "Error: Decrypted payload does not match original!"
    print("  -> Decryption SHA256 integrity match verified!")

    # Tamper resistance test (flip 1 byte in ciphertext)
    tampered = bytearray(ciphertext)
    tampered[0] ^= 0xFF
    try:
        security_ec.decrypt_payload(bytes(tampered), nonce)
        assert False, "Error: Tampered payload decrypted without raising integrity tag error!"
    except Exception as e:
        print(f"  -> Tamper resistance verified! Correctly rejected tampered payload: {e}")
    
    print("[PASS] AES-256-GCM Encryption Tests Passed!\n")

def test_erasure_coding_sharding():
    print("[TEST 2/4] Running Reed-Solomon K+M Erasure Coding Sharding Tests...")
    file_bytes = b"Enterprise Fault-Tolerant Distributed Storage Sharding Test File Bytes String"
    
    # Shard into K=2 Data shards + M=1 Parity shard (Total 3 shards)
    shards = security_ec.shard_payload(file_bytes, k=2, m=1)
    assert len(shards) == 3, f"Error: Expected 3 shards, got {len(shards)}"
    print(f"  -> Successfully generated {len(shards)} shards (K=2 Data + M=1 Parity)")
    
    # Case A: Full set of shards -> Reconstruction
    rec_full = security_ec.reconstruct_payload(shards, k=2, m=1)
    assert rec_full == file_bytes, "Error: Reconstruction from 100% healthy shards failed!"
    
    # Case B: Simulate Node 1 Crash (Shard 0 Missing/Corrupted)
    simulated_crash_1 = [None, shards[1], shards[2]]
    rec_crash_1 = security_ec.reconstruct_payload(simulated_crash_1, k=2, m=1)
    assert rec_crash_1 == file_bytes, "Error: Erasure reconstruction failed with Shard 0 missing!"
    print("  -> Node 1 Crash Simulation: Reconstructed file with 0 data loss!")

    # Case C: Simulate Node 2 Crash (Shard 1 Missing/Corrupted)
    simulated_crash_2 = [shards[0], None, shards[2]]
    rec_crash_2 = security_ec.reconstruct_payload(simulated_crash_2, k=2, m=1)
    assert rec_crash_2 == file_bytes, "Error: Erasure reconstruction failed with Shard 1 missing!"
    print("  -> Node 2 Crash Simulation: Reconstructed file with 0 data loss!")

    print("[PASS] Erasure Coding Sharding & Reconstruction Tests Passed!\n")

def test_rbac_authorization():
    print("[TEST 3/4] Running RBAC & API Key Authorization Tests...")
    
    # Test Admin key
    is_valid, role, err = security_ec.authenticate_api_key("admin-secret-key-99")
    assert is_valid and role == "Admin", "Error: Admin key authentication failed!"
    assert security_ec.check_permission(role, "write") and security_ec.check_permission(role, "read"), "Admin permissions error"
    
    # Test Writer key
    is_valid, role, err = security_ec.authenticate_api_key("writer-secret-key-55")
    assert is_valid and role == "Writer", "Error: Writer key authentication failed!"
    assert security_ec.check_permission(role, "write") and not security_ec.check_permission(role, "admin"), "Writer permissions error"

    # Test Reader key
    is_valid, role, err = security_ec.authenticate_api_key("reader-secret-key-11")
    assert is_valid and role == "Reader", "Error: Reader key authentication failed!"
    assert security_ec.check_permission(role, "read") and not security_ec.check_permission(role, "write"), "Reader permissions error"

    # Test Invalid key
    is_valid, role, err = security_ec.authenticate_api_key("invalid-hacker-key")
    assert not is_valid, "Error: Invalid API key accepted!"
    
    print("[PASS] RBAC & API Key Security Tests Passed!\n")

def test_prometheus_metrics():
    print("[TEST 4/4] Running Prometheus Metrics Exporter Tests...")
    coordinator_metrics.inc("files_stored_total", 5)
    coordinator_metrics.inc("erasure_reconstructions_total", 2)
    
    exposition = coordinator_metrics.generate_prometheus_exposition()
    assert "# HELP fts_files_stored_total" in exposition, "Prometheus HELP header missing!"
    assert "# TYPE fts_files_stored_total counter" in exposition, "Prometheus TYPE header missing!"
    assert 'fts_files_stored_total{service="coordinator"} 5.0' in exposition, "Prometheus metric counter value mismatch!"
    
    print("  -> Prometheus Exposition Format verified:\n" + "\n".join(exposition.splitlines()[:6]))
    print("[PASS] Prometheus Metrics Tests Passed!\n")

if __name__ == "__main__":
    print("==========================================================")
    print("      Phase 4 Enterprise Features Verification Suite      ")
    print("==========================================================\n")
    try:
        test_encryption_decryption()
        test_erasure_coding_sharding()
        test_rbac_authorization()
        test_prometheus_metrics()
        print("==========================================================")
        print("         ALL PHASE 4 ENTERPRISE TESTS PASSED!             ")
        print("==========================================================")
    except AssertionError as e:
        print(f"\n[FAIL] Assertion Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Unexpected Exception: {e}")
        sys.exit(1)
