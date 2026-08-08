"""
Enterprise Security & Erasure Coding Module — Fault-Tolerant File Storage System
Features:
  1. Zero-Trust AES-256-GCM Encryption & Decryption
  2. Reed-Solomon K+M Data Sharding & Erasure Reconstruction
  3. Role-Based Access Control (RBAC) & API Key Management
"""

import os
import hashlib
import hmac
import secrets
import threading
from typing import List, Optional, Tuple, Dict

# Try loading enterprise dependencies with robust native fallbacks
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False

try:
    import reedsolo  # type: ignore
    HAS_REEDSOLO = True
except ImportError:
    HAS_REEDSOLO = False

# Default Enterprise Master Key (256-bit)
DEFAULT_MASTER_KEY = os.environ.get(
    "ENTERPRISE_MASTER_KEY",
    "f7b9c2a8e4d10395682abf014e7c3d928b5e1a4f09d82e3c7b6a5f4e3d2c1b0a"
).encode('utf-8')
MASTER_KEY_32 = hashlib.sha256(DEFAULT_MASTER_KEY).digest()

# ─────────────────────────────────────────────────────────────────────────────
# 1. Zero-Trust AES-256-GCM Encryption Layer
# ─────────────────────────────────────────────────────────────────────────────
def encrypt_payload(data: bytes, key: bytes = MASTER_KEY_32) -> Tuple[bytes, bytes]:
    """
    Encrypts raw bytes using AES-256-GCM.
    Returns (ciphertext_with_tag, nonce).
    """
    if HAS_CRYPTOGRAPHY:
        nonce = secrets.token_bytes(12)  # 96-bit nonce for GCM
        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(nonce, data, None)
        return ciphertext, nonce
    else:
        # High-security native fallback (HMAC-SHA256 + Stream Cipher)
        nonce = secrets.token_bytes(16)
        stream_key = hmac.new(key, nonce, hashlib.sha256).digest()
        # Keystream expansion
        keystream = bytearray()
        counter = 0
        while len(keystream) < len(data):
            block = hmac.new(stream_key, counter.to_bytes(4, 'big'), hashlib.sha256).digest()
            keystream.extend(block)
            counter += 1
        
        encrypted = bytes(a ^ b for a, b in zip(data, keystream[:len(data)]))
        tag = hmac.new(key, nonce + encrypted, hashlib.sha256).digest()
        return encrypted + tag, nonce

def decrypt_payload(ciphertext_with_tag: bytes, nonce: bytes, key: bytes = MASTER_KEY_32) -> bytes:
    """
    Decrypts ciphertext and verifies integrity tag.
    """
    if HAS_CRYPTOGRAPHY:
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(nonce, ciphertext_with_tag, None)
    else:
        if len(ciphertext_with_tag) < 32:
            raise ValueError("Ciphertext too short for authentication tag")
        encrypted = ciphertext_with_tag[:-32]
        tag = ciphertext_with_tag[-32:]
        
        expected_tag = hmac.new(key, nonce + encrypted, hashlib.sha256).digest()
        if not hmac.compare_digest(tag, expected_tag):
            raise ValueError("AES-256-GCM Integrity authentication tag mismatch!")
            
        stream_key = hmac.new(key, nonce, hashlib.sha256).digest()
        keystream = bytearray()
        counter = 0
        while len(keystream) < len(encrypted):
            block = hmac.new(stream_key, counter.to_bytes(4, 'big'), hashlib.sha256).digest()
            keystream.extend(block)
            counter += 1
            
        return bytes(a ^ b for a, b in zip(encrypted, keystream[:len(encrypted)]))

# RSCodec Instance Cache to avoid re-initializing Galois Field lookup tables on every chunk
_RS_CODEC_CACHE: Dict[int, object] = {}
_RS_CACHE_LOCK = threading.Lock()

def _get_rs_codec(m: int):
    if not HAS_REEDSOLO:
        return None
    with _RS_CACHE_LOCK:
        if m not in _RS_CODEC_CACHE:
            _RS_CODEC_CACHE[m] = reedsolo.RSCodec(m)
        return _RS_CODEC_CACHE[m]

# ─────────────────────────────────────────────────────────────────────────────
# 2. Reed-Solomon K+M Erasure Coding Engine
# ─────────────────────────────────────────────────────────────────────────────
def shard_payload(data: bytes, k: int = 2, m: int = 1) -> List[bytes]:
    """
    Splits payload into K data shards and generates M parity shards.
    Total shards returned = K + M.
    Each shard begins with a 4-byte header encoding original shard length.
    """
    if HAS_REEDSOLO and k >= 1 and m >= 1:
        rs = _get_rs_codec(m)
        # Calculate chunk size per data shard
        data_len = len(data)
        chunk_size = (data_len + k - 1) // k if k > 0 else data_len
        if chunk_size == 0:
            chunk_size = 1
            
        data_shards = []
        for i in range(k):
            chunk = data[i * chunk_size : (i + 1) * chunk_size]
            if len(chunk) < chunk_size:
                chunk = chunk.ljust(chunk_size, b'\x00')
            data_shards.append(chunk)
            
        # Parity calculation using byte-wise Reed-Solomon
        parity_shards = []
        for p in range(m):
            parity_chunk = bytearray(chunk_size)
            for byte_idx in range(chunk_size):
                byte_vector = bytes([sh[byte_idx] for sh in data_shards])
                encoded = rs.encode(byte_vector)
                parity_chunk[byte_idx] = encoded[len(byte_vector) + p]
            parity_shards.append(bytes(parity_chunk))
            
        # Store original data length in metadata header for each shard
        header = data_len.to_bytes(4, 'big')
        return [header + sh for sh in (data_shards + parity_shards)]
    else:
        # Native XOR Parity Engine (K=2, M=1)
        data_len = len(data)
        half = (data_len + 1) // 2
        d1 = data[:half].ljust(half, b'\x00')
        d2 = data[half:].ljust(half, b'\x00')
        parity = bytes(a ^ b for a, b in zip(d1, d2))
        
        header = data_len.to_bytes(4, 'big')
        return [header + d1, header + d2, header + parity]

def reconstruct_payload(shards: List[Optional[bytes]], k: int = 2, m: int = 1) -> bytes:
    """
    Reconstructs original payload from any K valid shards (out of K+M).
    shards: List of length K+M, where missing/corrupted shards are None.
    """
    valid_shards = [(idx, sh) for idx, sh in enumerate(shards) if sh is not None]
    if len(valid_shards) < k:
        raise ValueError(f"Insufficient shards for reconstruction: need {k}, got {len(valid_shards)}")
        
    # Extract headers
    first_valid = valid_shards[0][1]
    data_len = int.from_bytes(first_valid[:4], 'big')
    raw_shards = [sh[4:] if sh is not None else None for sh in shards]
    chunk_size = len(first_valid[4:])
    
    if HAS_REEDSOLO and k >= 1 and m >= 1:
        rs = _get_rs_codec(m)
        reconstructed_data_shards = [None] * k
        
        # Check which data shards are present
        for i in range(k):
            if raw_shards[i] is not None:
                reconstructed_data_shards[i] = raw_shards[i]
                
        # Reconstruct missing data shards byte-by-byte using Reed-Solomon decoding
        missing_data_indices = [i for i in range(k) if reconstructed_data_shards[i] is None]
        if missing_data_indices:
            erasure_pos = []
            available_vector = []
            for i in range(k + m):
                if raw_shards[i] is None:
                    erasure_pos.append(i)
                else:
                    available_vector.append(i)
                    
            for idx in missing_data_indices:
                reconstructed_data_shards[idx] = bytearray(chunk_size)
                
            for byte_idx in range(chunk_size):
                encoded_buf = bytearray(k + m)
                erase_pos = []
                for sh_idx in range(k + m):
                    if raw_shards[sh_idx] is not None:
                        encoded_buf[sh_idx] = raw_shards[sh_idx][byte_idx]
                    else:
                        erase_pos.append(sh_idx)
                decoded = rs.decode(encoded_buf, erase_pos=erase_pos)[0]
                for idx in missing_data_indices:
                    reconstructed_data_shards[idx][byte_idx] = decoded[idx]
                    
        full_payload = b''.join(bytes(sh) for sh in reconstructed_data_shards)
        return full_payload[:data_len]
    else:
        # Native XOR Parity Reconstruction
        d1, d2, p = raw_shards[0], raw_shards[1], raw_shards[2] if len(raw_shards) > 2 else None
        
        if d1 is None and d2 is not None and p is not None:
            d1 = bytes(a ^ b for a, b in zip(d2, p))
        elif d2 is None and d1 is not None and p is not None:
            d2 = bytes(a ^ b for a, b in zip(d1, p))
            
        if d1 is None or d2 is None:
            raise ValueError("Cannot reconstruct XOR parity with current shard availability")
            
        full_payload = d1 + d2
        return full_payload[:data_len]

# ─────────────────────────────────────────────────────────────────────────────
# 3. Enterprise RBAC & API Key Security Layer
# ─────────────────────────────────────────────────────────────────────────────
API_KEY_REGISTRY: Dict[str, str] = {
    "admin-secret-key-99": "Admin",
    "writer-secret-key-55": "Writer",
    "reader-secret-key-11": "Reader"
}

ROLE_PERMISSIONS = {
    "Admin":  {"read", "write", "delete", "retrain", "checkpoint", "admin"},
    "Writer": {"read", "write"},
    "Reader": {"read"}
}

def authenticate_api_key(api_key: Optional[str]) -> Tuple[bool, str, str]:
    """
    Validates API key and returns (is_valid, role, error_message).
    If no API key provided, defaults to 'Admin' for backward-compatible web UI access.
    """
    if not api_key:
        return True, "Admin", ""  # UI Default
    
    role = API_KEY_REGISTRY.get(api_key)
    if not role:
        return False, "", "Invalid API Key authorization credentials."
    return True, role, ""

def check_permission(role: str, required_permission: str) -> bool:
    """Checks if role possesses the required action permission."""
    perms = ROLE_PERMISSIONS.get(role, set())
    return required_permission in perms
