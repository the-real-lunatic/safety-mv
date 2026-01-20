from __future__ import annotations

from dataclasses import dataclass

from ...core.config import settings
from ...core.pipeline import PipelineContext, PipelineResult
from ..base import Strategy
from ..common_steps import (
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
class VideoChainStrategy(Strategy):
    strategy_id: str = "video_chain"

    def run(self, context: PipelineContext) -> PipelineResult:
        providers = build_providers(settings.pipeline_mode)
        duration = int(context.options.get("duration_seconds", 60))
        sentences = parse_sentences(context, providers)
        actions = extract_actions(sentences, providers)
        slot_seconds = settings.sora_slot_seconds
        scenes = plan_scenes(actions, duration, slot_seconds=slot_seconds)
        style = style_lock(context, providers)

        chain_seed = "start"
        for scene in scenes:
            scene["style"] = style
            scene["chain_seed"] = chain_seed
            scene["prompt"] = clip_prompt(scene, style)
            chain_seed = f"seed_{scene['index']}"

        clips = generate_clips(scenes, providers, duration_seconds=slot_seconds)
        music = generate_music("Video chain MV track", duration, providers)

        artifacts = [
            context.write_json("sentences.json", {"sentences": sentences}),
            context.write_json("actions.json", {"actions": actions}),
            context.write_json("scenes.json", {"scenes": scenes}),
            context.write_json("style_lock.json", {"style_lock": style}),
            context.write_json("clips.json", {"clips": clips}),
            context.write_json("music.json", {"music": music}),
        ]
        return PipelineResult(artifacts=artifacts, metadata={"strategy": self.strategy_id})
