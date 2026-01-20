from __future__ import annotations

from dataclasses import dataclass

from ...core.config import settings
from ...core.pipeline import PipelineContext, PipelineResult
from ...core.lyrics import generate_lyrics, lyrics_prompt
from ..base import Strategy
from ..common_artifacts import save_json
from ..common_steps import (
    beat_map,
    build_providers,
    clip_prompt,
    extract_actions,
    generate_clips,
    generate_music,
    parse_sentences,
    plan_scenes,
    style_lock,
)


@dataclass(slots=True)
class HybridOverlapStrategy(Strategy):
    strategy_id: str = "hybrid_overlap"

    def run(self, context: PipelineContext) -> PipelineResult:
        providers = build_providers(settings.pipeline_mode)
        duration = int(context.options.get("duration_seconds", 60))
        slot_seconds = settings.sora_slot_seconds
        beat = beat_map(duration, slot_seconds=slot_seconds)

        sentences = parse_sentences(context, providers)
        actions = extract_actions(sentences, providers)
        lyrics = generate_lyrics(context, providers)
        music = generate_music(f"Audio-first safety MV track. {lyrics_prompt(lyrics)}", duration, providers)
        scenes = plan_scenes(actions, duration, slot_seconds=slot_seconds)
        style = style_lock(context, providers)

        for scene in scenes:
            scene["style"] = style
            scene["overlap"] = 0.6
            scene["prompt"] = clip_prompt(scene, style)

        clips = generate_clips(scenes, providers, duration_seconds=slot_seconds)

        artifacts = [
            save_json(context, "music.json", {"music": music}),
            save_json(context, "beat_map.json", beat),
            save_json(context, "sentences.json", {"sentences": sentences}),
            save_json(context, "actions.json", {"actions": actions}),
            save_json(context, "lyrics.json", lyrics),
            save_json(context, "scenes.json", {"scenes": scenes}),
            save_json(context, "style_lock.json", {"style_lock": style}),
            save_json(context, "clips.json", {"clips": clips}),
        ]
        return PipelineResult(artifacts=artifacts, metadata={"strategy": self.strategy_id})
