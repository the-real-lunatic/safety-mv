from __future__ import annotations

from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

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
        lyrics = generate_lyrics(context, providers)
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

        music = generate_music(f"Safety MV track with style lock. {lyrics_prompt(lyrics)}", duration, providers)

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
