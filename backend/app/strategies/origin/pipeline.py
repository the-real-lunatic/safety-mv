from __future__ import annotations

from dataclasses import dataclass

from ...core.config import settings
from ...core.pipeline import PipelineContext, PipelineResult
from ..base import Strategy
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


@dataclass(slots=True)
class OriginStrategy(Strategy):
    strategy_id: str = "origin"

    def run(self, context: PipelineContext) -> PipelineResult:
        providers = build_providers(settings.pipeline_mode)
        sentences = parse_sentences(context, providers)
        actions = extract_actions(sentences, providers)
        slot_seconds = settings.sora_slot_seconds
        scenes = plan_scenes(actions, int(context.options.get("duration_seconds", 60)), slot_seconds=slot_seconds)
        style = style_lock(context, providers)
        beat = beat_map(int(context.options.get("duration_seconds", 60)), slot_seconds=slot_seconds)
        for scene in scenes:
            scene["style"] = style
            scene["prompt"] = None

        clips = generate_clips(scenes, providers, duration_seconds=slot_seconds)
        music = generate_music("Safety MV base track", int(context.options.get("duration_seconds", 60)), providers)

        artifacts = [
            context.write_json("sentences.json", {"sentences": sentences}),
            context.write_json("actions.json", {"actions": actions}),
            context.write_json("scenes.json", {"scenes": scenes}),
            context.write_json("style_lock.json", {"style_lock": style}),
            context.write_json("beat_map.json", beat),
            context.write_json("clips.json", {"clips": clips}),
            context.write_json("music.json", {"music": music}),
        ]
        return PipelineResult(artifacts=artifacts, metadata={"strategy": self.strategy_id})
