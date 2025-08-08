from enum import Enum
from typing import List, Dict, Any
class AIModel(Enum):
    GPT_4 = "gpt-4"
    GPT_4O = "gpt-4o"
    OLLAMA_DEEPSEEK_14B = "deepseek-r1:14b"
    OLLAMA_GEMMA_7B = "gemma:7b"
    GPT_5 = "gpt-5"
    GPT_5_MINI = "gpt-5-mini"
    GPT_5_NANO = "gpt-5-nano"
    GPT_5_CHAT = "gpt-5-chat"
    GPT_5_PRO = "gpt-5-pro"         # optional, for Pro-tier use
    GPT_5_THINKING = "gpt-5-thinking"  # optional, reasoning-focused variant