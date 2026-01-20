from __future__ import annotations

from dataclasses import dataclass

from ...core.config import settings
from ...core.pipeline import PipelineContext, PipelineResult
from ..base import Strategy
from ..common_steps import (
    build_providers,
    extract_actions,
    generate_music,
    parse_sentences,
    plan_scenes,
    style_lock,
)


@dataclass(slots=True)
class StoryboardKeyframesStrategy(Strategy):
    strategy_id: str = "storyboard_keyframes"

    def run(self, context: PipelineContext) -> PipelineResult:
        providers = build_providers(settings.pipeline_mode)
        duration = int(context.options.get("duration_seconds", 60))
        sentences = parse_sentences(context, providers)
        actions = extract_actions(sentences, providers)
        slot_seconds = settings.sora_slot_seconds
        scenes = plan_scenes(actions, duration, slot_seconds=slot_seconds)
        style = style_lock(context, providers)

        keyframes = []
        for scene in scenes:
            keyframes.append({
                "scene": scene,
                "prompt": f"Keyframe: {scene.get('action')} with style {style}",
            })

        music = generate_music("Storyboard MV track", duration, providers)

        artifacts = [
            context.write_json("sentences.json", {"sentences": sentences}),
            context.write_json("actions.json", {"actions": actions}),
            context.write_json("scenes.json", {"scenes": scenes}),
            context.write_json("style_lock.json", {"style_lock": style}),
            context.write_json("keyframes.json", {"keyframes": keyframes}),
            context.write_json("music.json", {"music": music}),
        ]
        return PipelineResult(artifacts=artifacts, metadata={"strategy": self.strategy_id})
