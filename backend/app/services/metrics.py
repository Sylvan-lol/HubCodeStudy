"""In-memory metrics for benchmark dashboard and product observability."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field


@dataclass
class MetricsCollector:
    _lock: threading.Lock = field(default_factory=threading.Lock)

    analyze_attempts: int = 0
    analyze_success: int = 0
    analyze_failures: int = 0
    analyze_cache_hits: int = 0

    chat_total: int = 0
    chat_first_token_ms_sum: float = 0.0
    chat_first_token_count: int = 0
    chat_evidence_hit: int = 0
    chat_effective: int = 0

    def record_analyze_finish(self, success: bool, cache_hit: bool = False) -> None:
        with self._lock:
            self.analyze_attempts += 1
            if success:
                self.analyze_success += 1
                if cache_hit:
                    self.analyze_cache_hits += 1
            else:
                self.analyze_failures += 1

    def record_chat_first_token_ms(self, ms: float) -> None:
        with self._lock:
            self.chat_first_token_ms_sum += ms
            self.chat_first_token_count += 1

    def record_chat_finish(self, evidence_nonempty: bool, answer_effective: bool) -> None:
        with self._lock:
            self.chat_total += 1
            if evidence_nonempty:
                self.chat_evidence_hit += 1
            if answer_effective:
                self.chat_effective += 1

    def snapshot(self) -> dict:
        with self._lock:
            ar = self.analyze_attempts
            cr = self.chat_total
            ft_n = self.chat_first_token_count
            return {
                "analyze_success_rate": round(self.analyze_success / ar, 4) if ar else None,
                "analyze_attempts": ar,
                "analyze_success": self.analyze_success,
                "analyze_failures": self.analyze_failures,
                "analyze_cache_hit_rate": round(self.analyze_cache_hits / max(1, self.analyze_success), 4)
                if self.analyze_success
                else 0.0,
                "analyze_cache_hits": self.analyze_cache_hits,
                "first_token_latency_avg_ms": round(self.chat_first_token_ms_sum / ft_n, 2) if ft_n else None,
                "first_token_samples": ft_n,
                "evidence_hit_rate": round(self.chat_evidence_hit / cr, 4) if cr else None,
                "answer_effectiveness_rate": round(self.chat_effective / cr, 4) if cr else None,
                "chat_total": cr,
                "chat_evidence_hits": self.chat_evidence_hit,
                "chat_effective_answers": self.chat_effective,
            }


metrics = MetricsCollector()
