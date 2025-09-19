import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class BitgetConfig:
    """Bitget API configuration"""
    api_key: str
    secret_key: str
    passphrase: str
    base_url: str = "https://api.bitget.com"
    
    @classmethod
    def from_env(cls) -> "BitgetConfig":
        """Create config from environment variables"""
        return cls(
            api_key=os.getenv("BITGET_API_KEY", "bg_680026a00a63d58058c738c952ce67a2"),
            secret_key=os.getenv("BITGET_SECRET_KEY", "7abac4a9404e82830db5f9db5e867a8370c7e59dc74e52615c59552d0afbd7c9"),
            passphrase=os.getenv("BITGET_PASSPHRASE", "22Dominic22")
        )