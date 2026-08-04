"""RFC-3161 time-stamping — the external witness for the proof chain.

The chain alone holds only against outsiders: self-hosted, the club controls
the server and could rewrite chain and data together. A token from an
independent TSA over the chain head is the one statement outside that reach —
"this hash existed no later than this moment, says someone else".

The request is built by hand rather than through an ASN.1 library: a
TimeStampReq for SHA-256 with `certReq` is a fixed 61-byte DER structure with
a 32-byte hole, and a dependency for that would be all surface. The response
token is stored opaque and verified with standard tooling
(`openssl ts -reply ... -verify`) — this code witnesses, it does not judge.
"""

import hashlib

import httpx

# TimeStampReq { version 1, messageImprint { sha256, <hash> }, certReq TRUE },
# DER. See RFC 3161 §2.4.1.
_TSQ_PREFIX = bytes.fromhex(
    "3039"  # SEQUENCE, 57 bytes
    "020101"  # version INTEGER 1
    "3031"  # messageImprint SEQUENCE, 49 bytes
    "300d0609608648016503040201"  # AlgorithmIdentifier: OID sha256
    "0500"  # ... parameters NULL
    "0420"  # hashedMessage OCTET STRING, 32 bytes
)
_TSQ_SUFFIX = bytes.fromhex("0101ff")  # certReq BOOLEAN TRUE


def build_timestamp_query(chain_hash_hex: str) -> bytes:
    """The DER TimeStampReq for a chain head.

    The imprint hashes the *hex string* of the chain head, not raw bytes —
    arbitrary but fixed, and it must stay fixed: verifying an old token later
    means recomputing exactly this imprint.
    """
    imprint = hashlib.sha256(chain_hash_hex.encode()).digest()
    return _TSQ_PREFIX + imprint + _TSQ_SUFFIX


class TsaClient:
    """One POST per anchor. Failures raise — the caller decides that a missed
    anchor is retried next interval rather than papered over."""

    def __init__(self, url: str, *, timeout_seconds: float = 15.0) -> None:
        self.url = url
        self.timeout_seconds = timeout_seconds

    async def timestamp(self, chain_hash_hex: str) -> bytes:
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                self.url,
                content=build_timestamp_query(chain_hash_hex),
                headers={"Content-Type": "application/timestamp-query"},
            )
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "application/timestamp-reply" not in content_type:
            raise ValueError(f"TSA answered with {content_type or 'no content type'}")
        return response.content
