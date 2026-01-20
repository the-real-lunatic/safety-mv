from __future__ import annotations

from dataclasses import dataclass

from ...core.config import settings
from ...core.pipeline import PipelineContext, PipelineResult
from ..base import Strategy
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
class MixAudioAnchorStrategy(Strategy):
    strategy_id: str = "mix_audio_anchor"

    def run(self, context: PipelineContext) -> PipelineResult:
        providers = build_providers(settings.pipeline_mode)
        duration = int(context.options.get("duration_seconds", 60))
        music = generate_music("Audio-first MV track with anchor cues", duration, providers)
        slot_seconds = settings.sora_slot_seconds
        beat = beat_map(duration, slot_seconds=slot_seconds)

        sentences = parse_sentences(context, providers)
        actions = extract_actions(sentences, providers)
        scenes = plan_scenes(actions, duration, slot_seconds=slot_seconds)
        style = style_lock(context, providers)

        for scene in scenes:
            scene["anchor"] = f"beat_{scene['index']}"
            scene["style"] = style
            scene["prompt"] = clip_prompt(scene, style)

        clips = generate_clips(scenes, providers, duration_seconds=slot_seconds)

        artifacts = [
            context.write_json("music.json", {"music": music}),
            context.write_json("beat_map.json", beat),
            context.write_json("sentences.json", {"sentences": sentences}),
            context.write_json("actions.json", {"actions": actions}),
            context.write_json("scenes.json", {"scenes": scenes}),
            context.write_json("style_lock.json", {"style_lock": style}),
            context.write_json("clips.json", {"clips": clips}),
        ]
        return PipelineResult(artifacts=artifacts, metadata={"strategy": self.strategy_id})
