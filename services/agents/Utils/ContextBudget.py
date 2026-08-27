import json


DEFAULT_BUDGET_TOKENS = 1500
_CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    try:
        import tiktoken
    except ImportError:
        return max(1, (len(text) + _CHARS_PER_TOKEN - 1) // _CHARS_PER_TOKEN)
    encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))


class ContextBudget:
    """Fill a context payload up to a fixed token budget and report what fit.

    Every retrieval condition in the experiment goes through this class, so the
    conditions differ only in which entries are offered, never in how much text
    reaches the model.
    """

    def __init__(self, max_tokens: int = DEFAULT_BUDGET_TOKENS, reserve_tokens: int = 0):
        if max_tokens < 0:
            raise ValueError("max_tokens must not be negative")
        if reserve_tokens < 0:
            raise ValueError("reserve_tokens must not be negative")
        self.max_tokens = max_tokens
        self.reserve_tokens = reserve_tokens
        self.entries = []
        self.used_tokens = 0
        self.rejected = 0

    @property
    def available(self) -> int:
        return max(0, self.max_tokens - self.reserve_tokens - self.used_tokens)

    def offer(self, entry, text: str = None) -> bool:
        payload = text if text is not None else json.dumps(entry, sort_keys=True, default=str)
        cost = estimate_tokens(payload)
        if cost > self.available:
            self.rejected += 1
            return False
        self.entries.append(entry)
        self.used_tokens += cost
        return True

    def fill(self, candidates, text_of=None) -> list:
        for candidate in candidates:
            if self.available <= 0:
                self.rejected += 1
                continue
            self.offer(candidate, text_of(candidate) if text_of else None)
        return self.entries

    def report(self) -> dict:
        return {
            "budget_tokens": self.max_tokens,
            "reserve_tokens": self.reserve_tokens,
            "used_tokens": self.used_tokens,
            "remaining_tokens": self.available,
            "entries_kept": len(self.entries),
            "entries_rejected": self.rejected,
        }
