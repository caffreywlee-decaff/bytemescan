"""bytemescan — 식약처 공개 명부에 상품 주장(기능성)을 대조하는 얇은 MCP/CLI.

공개 데이터만 쓴다. 위법 판정이 아니라 '공식 보고와 같은가' 대조까지.
"""
from .check import lookup_cosmetic, check_cosmetic_claim  # noqa: F401
from .compare import compare_claim  # noqa: F401

__version__ = "0.1.0"
