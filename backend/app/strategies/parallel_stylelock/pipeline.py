from __future__ import annotations

from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

from ...core.config import settings
from ...core.pipeline import PipelineContext, PipelineResult
from ..base import Strategy
from ..common_steps import (
    beat_map,
    build_providers,
    clip_prompt,
    extract_actions,
    generate_music,
    parse_sentences,
    plan_scenes,
    style_lock,
)


@dataclass(slots=True)
class ParallelStyleLockStrategy(Strategy):
    strategy_id: str = "parallel_stylelock"

    def run(self, context: PipelineContext) -> PipelineResult:
        providers = build_providers(settings.pipeline_mode)
        duration = int(context.options.get("duration_seconds", 60))
        sentences = parse_sentences(context, providers)
        actions = extract_actions(sentences, providers)
        slot_seconds = settings.sora_slot_seconds
        scenes = plan_scenes(actions, duration, slot_seconds=slot_seconds)
        style = style_lock(context, providers)
        beat = beat_map(duration, slot_seconds=slot_seconds)

        for scene in scenes:
            scene["style"] = style
            scene["prompt"] = clip_prompt(scene, style)

        if providers.sora is None:
            clips = [
                {"scene": scene, "video": {"mock": True, "prompt": scene["prompt"], "duration": slot_seconds}}
                for scene in scenes
            ]
        else:
            with ThreadPoolExecutor(max_workers=min(4, len(scenes))) as executor:
                futures = [
                    executor.submit(providers.sora.generate, scene["prompt"], slot_seconds) for scene in scenes
                ]
                clips = []
                for scene, future in zip(scenes, futures, strict=True):
                    clips.append({"scene": scene, "video": future.result()})

        music = generate_music("Safety MV track with style lock", duration, providers)

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
