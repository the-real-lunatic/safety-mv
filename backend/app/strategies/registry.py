from __future__ import annotations

from typing import Dict

from .base import Strategy
from .hybrid_overlap.pipeline import HybridOverlapStrategy
from .mix_audio_anchor.pipeline import MixAudioAnchorStrategy
from .origin.pipeline import OriginStrategy
from .parallel_stylelock.pipeline import ParallelStyleLockStrategy
from .sequential_anchor.pipeline import SequentialAnchorStrategy
from .storyboard_keyframes.pipeline import StoryboardKeyframesStrategy
from .video_chain.pipeline import VideoChainStrategy


_STRATEGIES: Dict[str, Strategy] = {
    "origin": OriginStrategy(),
    "parallel_stylelock": ParallelStyleLockStrategy(),
    "sequential_anchor": SequentialAnchorStrategy(),
    "hybrid_overlap": HybridOverlapStrategy(),
    "storyboard_keyframes": StoryboardKeyframesStrategy(),
    "mix_audio_anchor": MixAudioAnchorStrategy(),
    "video_chain": VideoChainStrategy(),
}


def get_strategy(strategy_id: str) -> Strategy:
    return _STRATEGIES[strategy_id]


def strategy_ids() -> list[str]:
    return sorted(_STRATEGIES.keys())
