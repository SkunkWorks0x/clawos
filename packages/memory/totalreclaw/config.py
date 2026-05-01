"""
TotalReclaw Configuration
All tuneable defaults in one place. Override per-agent as needed.
"""

# ── Retrieval Settings ────────────────────────────────────────────────
DEFAULT_TOKEN_BUDGET = 2000
MAX_MEMORIES_PER_LAYER = 20

# ── Reflection Settings ──────────────────────────────────────────────
REFLECTION_KEEP_RECENT = 5
REFLECTION_DECAY_PENALTY = 2

# ── Capture Settings ─────────────────────────────────────────────────
DEFAULT_CAPTURE_IMPORTANCE = 5

# ── Storage Settings ─────────────────────────────────────────────────
DEFAULT_DB_PATH = "./totalreclaw.db"

# ── Version ──────────────────────────────────────────────────────────
VERSION = "0.1.0"
PRODUCT_NAME = "TotalReclaw"
