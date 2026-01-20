from __future__ import annotations

from dataclasses import dataclass

from ...core.config import settings
from ...core.pipeline import PipelineContext, PipelineResult
from ..base import Strategy
from ..common_artifacts import save_json
from ..common_steps import (
    beat_map,
    build_providers,
    extract_actions,
    generate_clips,
    generate_music,
    parse_sentences,
    plan_scenes,
    style_lock,
)
from ...core.lyrics import generate_lyrics, lyrics_prompt


@dataclass(slots=True)
class OriginStrategy(Strategy):
    strategy_id: str = "origin"

    def run(self, context: PipelineContext) -> PipelineResult:
        providers = build_providers(settings.pipeline_mode)
        sentences = parse_sentences(context, providers)
        actions = extract_actions(sentences, providers)
        lyrics = generate_lyrics(context, providers)
        slot_seconds = settings.sora_slot_seconds
        scenes = plan_scenes(actions, int(context.options.get("duration_seconds", 60)), slot_seconds=slot_seconds)
        style = style_lock(context, providers)
        beat = beat_map(int(context.options.get("duration_seconds", 60)), slot_seconds=slot_seconds)
        for scene in scenes:
            scene["style"] = style
            scene["prompt"] = None

        clips = generate_clips(scenes, providers, duration_seconds=slot_seconds)
        music = generate_music(
            f"Safety MV base track. {lyrics_prompt(lyrics)}",
            int(context.options.get("duration_seconds", 60)),
            providers,
        )

        artifacts = [
            save_json(context, "sentences.json", {"sentences": sentences}),
            save_json(context, "actions.json", {"actions": actions}),
            save_json(context, "lyrics.json", lyrics),
            save_json(context, "scenes.json", {"scenes": scenes}),
            save_json(context, "style_lock.json", {"style_lock": style}),
            save_json(context, "beat_map.json", beat),
            save_json(context, "clips.json", {"clips": clips}),
            save_json(context, "music.json", {"music": music}),
        ]
        return PipelineResult(artifacts=artifacts, metadata={"strategy": self.strategy_id})
