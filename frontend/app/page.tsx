"use client";

import { useMemo, useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Sparkles, Video, Check } from "lucide-react";

const videoVibes = [
  { id: "minimal", label: "Minimal" },
  { id: "corporate", label: "Corporate" },
  { id: "modern", label: "Modern" },
  { id: "cute", label: "Cute" },
] as const;

type VideoVibeId = (typeof videoVibes)[number]["id"];

const musicGenres = [
  { id: "hiphop", label: "힙합" },
  { id: "jazz", label: "재즈" },
  { id: "trot", label: "트로트" },
  { id: "rnb", label: "알앤비" },
  { id: "ballad", label: "발라드" },
  { id: "rock", label: "락" },
  { id: "dance", label: "댄스" },
  { id: "kpop", label: "케이팝" },
] as const;

type MusicGenreId = (typeof musicGenres)[number]["id"];

export function VideoGeneratorForm() {
  const router = useRouter();

  const [guidelines, setGuidelines] = useState("");
  const [length, setLength] = useState<"30s" | "45s">("30s");
  const [selectedStyles, setSelectedStyles] = useState<VideoVibeId[]>([]);
  const [selectedGenres, setSelectedGenres] = useState<MusicGenreId | null>(null);
  const [additionalRequirements, setAdditionalRequirements] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);

  // 타이머 cleanup용
  const timeoutRef = useRef<number | null>(null);
  useEffect(() => {
    return () => {
      if (timeoutRef.current) window.clearTimeout(timeoutRef.current);
    };
  }, []);

  const handleStyleToggle = (styleId: VideoVibeId) => {
    setSelectedStyles((prev) => {
      if (prev.includes(styleId)) return prev.filter((id) => id !== styleId);
      if (prev.length >= 2) return [...prev.slice(1), styleId]; // keep latest 2
      return [...prev, styleId];
    });
  };
  const handleGenreSelect = (genre: MusicGenreId) => {
    setSelectedGenres((prev) => (prev === genre ? null : genre));
  };
  
  const isFormValid = useMemo(() => {
    return guidelines.trim().length > 0 && selectedStyles.length > 0 && selectedGenres;
  }, [guidelines, selectedStyles, selectedGenres]);

  const helperText = useMemo(() => {
    if (!guidelines.trim()) return "Enter safety guidelines to continue";
    if (selectedStyles.length === 0) return "Select at least one visual style";
    if (!selectedGenres) return "Select music genre";
    return "";
  }, [guidelines, selectedStyles, selectedGenres]);

  const handleGenerate = async () => {
    if (!isFormValid || isGenerating) return;

    setIsGenerating(true);

    window.setTimeout(() => {
      setIsGenerating(false);
      console.log("Video generated with:", {
        guidelines,
        length,
        selectedStyles,
        selectedGenres,
        additionalRequirements,
      });
    }, 2000);
    const payload = {
      guidelines,
      length,
      selectedStyles,
      selectedGenres,
      additionalRequirements,
    };

    try {
      const res = await fetch("/post_job", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        // 서버가 에러 바디를 json/text로 줄 수도 있으니 안전 처리
        const text = await res.text().catch(() => "");
        throw new Error(text || `POST /post_job failed (${res.status})`);
      }

      // (선택) jobId를 받는다면 나중에 polling 등에 사용 가능
      // const data = await res.json().catch(() => null);
      // const jobId = data?.job_id;

      // 지금은 "10초 후 이동" 임시 로직
      timeoutRef.current = window.setTimeout(() => {
        router.push("/lyricselection");
      }, 10_000);
    } catch (err: any) {
      console.error("Error posting job:", err);
      setIsGenerating(false);
      // todo! 일단 넘어감. 백 연결 후 삭제
      router.push("/lyricselection");
      return;
    }

  };

  

  return (
    <div className="space-y-8">
      {/* Header */}
      <header className="space-y-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-500/20">
            <Video className="w-5 h-5 text-white" />
          </div>
          <div className="space-y-0.5">
            <h1 className="text-3xl md:text-4xl text-white tracking-tight">
              Safety Guidelines Video Generator
            </h1>
            <p className="text-gray-400 text-base md:text-lg">
              Transform your safety guidelines into engaging video content
            </p>
          </div>
        </div>
      </header>

      {/* Card: Guidelines */}
      <section className="rounded-2xl border border-gray-800/70 bg-[#121217] p-5 md:p-6 shadow-sm">
        <div className="flex items-end justify-between gap-4">
          <div>
            <label htmlFor="guidelines" className="text-gray-200 text-sm">
              Safety Guidelines
            </label>
            <p className="text-gray-500 text-sm mt-1">
              절차, 장비, 금지사항, 비상대응 등을 구체적으로 써줘.
            </p>
          </div>
          <span className="text-xs text-gray-500">
            {guidelines.trim().length}/2000
          </span>
        </div>

        <textarea
          id="guidelines"
          value={guidelines}
          onChange={(e) => setGuidelines(e.target.value.slice(0, 2000))}
          placeholder="Enter your safety guidelines here..."
          className="mt-4 min-h-[190px] w-full resize-none rounded-2xl bg-[#0f0f14] border border-gray-800 px-4 py-3 text-gray-100 placeholder:text-gray-600 outline-none focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/15"
        />
      </section>

      {/* Card: Options */}
      <section className="rounded-2xl border border-gray-800/70 bg-[#121217] p-5 md:p-6 space-y-6 shadow-sm">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h2 className="text-gray-100 text-lg font-medium">Options</h2>
            <p className="text-gray-500 text-sm mt-1">
              길이와 스타일을 고르면 자동으로 구성해줘.
            </p>
          </div>
        </div>

        <div className="grid gap-6 md:grid-cols-2">
          {/* Length */}
          <div className="space-y-2">
            <label htmlFor="length" className="text-gray-200 text-sm">
              Length
            </label>
            <div className="relative">
              <select
                id="length"
                value={length}
                onChange={(e) => setLength(e.target.value as "30s" | "45s")}
                className="w-full appearance-none rounded-xl bg-[#0f0f14] border border-gray-800 h-11 px-4 pr-10 text-gray-100 outline-none focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/15"
              >
                <option value="30s">30 seconds</option>
                <option value="45s">45 seconds</option>
              </select>

              <svg
                className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-500"
                viewBox="0 0 20 20"
                fill="currentColor"
                aria-hidden="true"
              >
                <path
                  fillRule="evenodd"
                  d="M5.23 7.21a.75.75 0 011.06.02L10 10.94l3.71-3.7a.75.75 0 111.06 1.06l-4.24 4.24a.75.75 0 01-1.06 0L5.21 8.29a.75.75 0 01.02-1.08z"
                  clipRule="evenodd"
                />
              </svg>
            </div>
          </div>

          {/* Additional */}
          <div className="space-y-2">
            <label htmlFor="additional" className="text-gray-200 text-sm">
              Additional Requirements{" "}
              <span className="text-gray-500">(optional)</span>
            </label>
            <textarea
              id="additional"
              value={additionalRequirements}
              onChange={(e) => setAdditionalRequirements(e.target.value)}
              placeholder="Tone, forbidden elements, specific scenes, etc."
              className="min-h-[110px] w-full resize-none rounded-2xl bg-[#0f0f14] border border-gray-800 px-4 py-3 text-gray-100 placeholder:text-gray-600 outline-none focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/15"
            />
          </div>
        </div>
{/* Visual Styles */}
        <div className="space-y-3">
          <div className="flex items-baseline justify-between gap-3">
            <div>
              <p className="text-gray-200 text-sm">
                Visual Style{" "}
                <span className="text-gray-500 text-xs ml-2">(select 1-2)</span>
                <span className="inline-flex items-center gap-2 rounded-full border border-gray-800 bg-[#0f0f14] px-3 py-1 text-xs text-gray-400">
                Selected: <b className="text-gray-200">{selectedStyles.length}</b>/2
              </span>
              </p>
              <p className="text-gray-500 text-sm mt-1">
                2개까지 선택할 수 있어요.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
            {videoVibes.map((vibe) => {
              const active = selectedStyles.includes(vibe.id);
              return (
                <button
                  key={vibe.id}
                  type="button"
                  onClick={() => handleStyleToggle(vibe.id)}
                  className={[
                    "group relative flex items-center justify-between",
                    "rounded-xl border px-3 py-2 text-sm",
                    "transition-all",
                    "focus:outline-none focus:ring-2 focus:ring-cyan-500/20",
                    active
                      ? "border-cyan-500/70 bg-cyan-500/10 text-cyan-200"
                      : "border-gray-800 bg-[#0f0f14] text-gray-300 hover:border-gray-700 hover:bg-[#14141a]",
                  ].join(" ")}
                >
                  <span className="truncate">{vibe.label}</span>
                  <span
                    className={[
                      "ml-3 inline-flex h-6 w-6 items-center justify-center rounded-lg border",
                      active
                        ? "border-cyan-500/40 bg-cyan-500/15 text-cyan-200"
                        : "border-gray-800 bg-transparent text-gray-600 group-hover:text-gray-400",
                    ].join(" ")}
                    aria-hidden="true"
                  >
                    {active ? <Check className="h-4 w-4" /> : null}
                  </span>
                </button>
              );
            })}
          </div>

          {selectedStyles.length >= 2 && (
            <p className="text-xs text-gray-500">
              2개 이상 선택 시 가장 최근에 선택한 스타일로 대체됩니다.
            </p>
          )}
        </div>
        {/* Music Genres */}
<div className="space-y-3">
  <div>
    <p className="text-gray-200 text-sm">
      Music Genres{" "}
      <span className="text-gray-500 text-xs ml-2">(select 1)</span>
    </p>
    <p className="text-gray-500 text-sm mt-1">
      1개만 선택할 수 있어요.
    </p>
  </div>

  <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
    {musicGenres.map((genre) => {
      const active = selectedGenres === genre.id;

      return (
        <button
          key={genre.id}
          type="button"
          onClick={() => handleGenreSelect(genre.id)}
          className={[
            "group relative flex items-center justify-between",
            "rounded-xl border px-3 py-2 text-sm transition-all",
            "focus:outline-none focus:ring-2 focus:ring-cyan-500/20",
            active
              ? "border-cyan-500/70 bg-cyan-500/10 text-cyan-200"
              : "border-gray-800 bg-[#0f0f14] text-gray-300 hover:border-gray-700 hover:bg-[#14141a]",
          ].join(" ")}
        >
          <span className="truncate">{genre.label}</span>
          <span
            className={[
              "ml-3 inline-flex h-6 w-6 items-center justify-center rounded-lg border",
              active
                ? "border-cyan-500/40 bg-cyan-500/15 text-cyan-200"
                : "border-gray-800 bg-transparent text-gray-600 group-hover:text-gray-400",
            ].join(" ")}
          >
            {active ? <Check className="h-4 w-4" /> : null}
          </span>
        </button>
      );
    })}
  </div>
</div>

      {/* Music Genres
        <div className="space-y-3">
          <div className="flex items-baseline justify-between gap-3">
            <div>
              <p className="text-gray-200 text-sm">
                Music Genres{" "}
                <span className="text-gray-500 text-xs ml-2">(select 1)</span>
              </p>
              <p className="text-gray-500 text-sm mt-1">
                1개만 선택할 수 있어요.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
            {musicGenres.map((genre) => {
              const active = selectedStyles.includes(genre.id);
              return (
                <button
                  key={genre.id}
                  type="button"
                  onClick={() => handleStyleToggle(genre.id)}
                  className={[
                    "group relative flex items-center justify-between",
                    "rounded-xl border px-3 py-2 text-sm",
                    "transition-all",
                    "focus:outline-none focus:ring-2 focus:ring-cyan-500/20",
                    active
                      ? "border-cyan-500/70 bg-cyan-500/10 text-cyan-200"
                      : "border-gray-800 bg-[#0f0f14] text-gray-300 hover:border-gray-700 hover:bg-[#14141a]",
                  ].join(" ")}
                >
                  <span className="truncate">{genre.label}</span>
                  <span
                    className={[
                      "ml-3 inline-flex h-6 w-6 items-center justify-center rounded-lg border",
                      active
                        ? "border-cyan-500/40 bg-cyan-500/15 text-cyan-200"
                        : "border-gray-800 bg-transparent text-gray-600 group-hover:text-gray-400",
                    ].join(" ")}
                    aria-hidden="true"
                  >
                    {active ? <Check className="h-4 w-4" /> : null}
                  </span>
                </button>
              );
            })}
          </div>
        </div> */}
      </section>

      {/* Generate */}
      <section className="space-y-3">
        <button
          type="button"
          onClick={handleGenerate}
          disabled={!isFormValid || isGenerating}
          className={[
            "w-full h-14 rounded-2xl text-white text-base",
            "bg-gradient-to-r from-cyan-500 to-blue-600",
            "hover:from-cyan-400 hover:to-blue-500",
            "shadow-lg shadow-cyan-500/15 hover:shadow-cyan-500/25 transition-all",
            "disabled:opacity-50 disabled:cursor-not-allowed",
            "flex items-center justify-center",
            "focus:outline-none focus:ring-2 focus:ring-cyan-500/25",
          ].join(" ")}
        >
          {isGenerating ? (
            <>
              <span className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin mr-2" />
              Generating Draft...
            </>
          ) : (
            <>
              <Sparkles className="w-5 h-5 mr-2" />
              {/* 시안 생성하기 */}
              Generate Draft
            </>
          )}
        </button>

        {!isFormValid && (
          <p className="text-center text-sm text-gray-500">{helperText}</p>
        )}
      </section>
    </div>
  );
}

export default function Page() {
  return (
    <main className="min-h-screen bg-[#0b0b0f]">
      <div className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-10 py-10 sm:py-14 lg:py-16">
        <div className="rounded-3xl border border-gray-800/60 bg-[#0f0f14]/60 backdrop-blur px-5 sm:px-8 py-7 sm:py-10 shadow-xl shadow-black/30">
          <VideoGeneratorForm />
        </div>
      </div>
    </main>
  );
}