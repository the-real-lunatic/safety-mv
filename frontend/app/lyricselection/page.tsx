"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Check, ArrowLeft, Sparkles } from "lucide-react";

/* =======================
   Types
======================= */

type LyricOption = {
  id: 1 | 2;
  text: string;
};

type JobStatus =
  | { status: "lyrics_processing"; progress?: number }
  | { status: "lyrics_done"; lyrics: { v1: string; v2: string } }
  | { status: "video_processing"; progress?: number }
  | { status: "video_done"; video_url: string }
  | { status: "error"; message?: string };

/* =======================
   API Utils
======================= */

async function fetchJobStatus(jobId: string): Promise<JobStatus> {
  const res = await fetch(`/job_status/${jobId}`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch job status");
  return res.json();
}

/* =======================
   Page
======================= */

export default function LyricSelectionPage() {
  const router = useRouter();

  /* ---------- State ---------- */

  const [jobId, setJobId] = useState<string | null>(null);

  const [options, setOptions] = useState<LyricOption[]>([]);
  const [selected, setSelected] = useState<1 | 2 | null>(null);

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  /* ---------- Polling ---------- */

  const pollingRef = useRef<number | null>(null);

  const stopPolling = () => {
    if (pollingRef.current) {
      window.clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  };

  /* =======================
     1️⃣ Mount: job_id 읽고
        가사 polling 시작
  ======================= */

  useEffect(() => {
    let id = sessionStorage.getItem("job_id");
    const mockup = true
    if (!id) {
        if (mockup){
            id = "mockup_job_id";
            console.log("Using mockup job_id");
        }
        else {
            router.replace("/");
            return;
        }
    }

    setJobId(id);
    startLyricsPolling(id);

    return () => stopPolling();
  }, []);

  /* =======================
     2️⃣ 가사 생성 polling
  ======================= */

  const startLyricsPolling = (id: string) => {
    if (pollingRef.current) return;

    pollingRef.current = window.setInterval(async () => {
      try {
        const status = await fetchJobStatus(id);

        if (status.status === "lyrics_done") {
          setOptions([
            { id: 1, text: status.lyrics.v1 },
            { id: 2, text: status.lyrics.v2 },
          ]);
          stopPolling();
        }

        if (status.status === "error") {
          throw new Error(status.message || "Lyrics generation failed");
        }
      } catch (e) {
        console.error(e);
        stopPolling();
        setErrorMsg("가사 생성 중 오류가 발생했어요.");
      }
    }, 1000);
  };

  /* =======================
     3️⃣ 영상 생성 polling
  ======================= */

  const startVideoPolling = (id: string) => {
    stopPolling();

    pollingRef.current = window.setInterval(async () => {
      try {
        const status = await fetchJobStatus(id);

        if (status.status === "video_done") {
          sessionStorage.setItem("video_url", status.video_url);
          stopPolling();
          router.push("/result");
        }

        if (status.status === "error") {
          throw new Error(status.message || "Video generation failed");
        }
      } catch (e) {
        console.error(e);
        stopPolling();
        setIsSubmitting(false);
        setErrorMsg("영상 생성 중 오류가 발생했어요.");
      }
    }, 1000);
  };

  /* =======================
     UI Logic
  ======================= */

  const canComplete = selected !== null && !isSubmitting;

  const handleBack = () => {
    if (isSubmitting) return;
    router.back();
  };

  /* =======================
     4️⃣ Complete 클릭
        → post_version
        → 영상 polling
  ======================= */

  const handleComplete = async () => {
    if (!canComplete || !jobId) return;

    setIsSubmitting(true);
    setErrorMsg(null);

    try {
      const res = await fetch("/post_version", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          job_id: jobId,
          version: selected,
        }),
      });

      if (!res.ok) {
        const text = await res.text().catch(() => "");
        throw new Error(text || "post_version failed");
      }

      startVideoPolling(jobId);
    } catch (err: any) {
      setErrorMsg(err?.message ?? "Request failed");
      setIsSubmitting(false);
    }
  };

  /* =======================
     Generating Overlay Text
  ======================= */

  const steps = useMemo(
    () => [
      "가사 선택을 반영하고 있어요",
      "장면을 구성하는 중…",
      "자막/타이밍을 맞추는 중…",
      "BGM 톤을 적용하는 중…",
      "최종 렌더링 거의 끝!",
    ],
    []
  );
  const [stepIndex, setStepIndex] = useState(0);

  useEffect(() => {
    if (!isSubmitting) return;

    const id = window.setInterval(() => {
      setStepIndex((p) => (p + 1) % steps.length);
    }, 7000);

    return () => window.clearInterval(id);
  }, [isSubmitting, steps.length]);

  /* =======================
     Render
  ======================= */

  return (
    <main className="min-h-screen bg-[#0b0b0f]">
      <div className="mx-auto max-w-4xl px-4 py-12 space-y-8">
        <header>
          <h1 className="text-3xl text-white">Lyrics Selection</h1>
          <p className="text-gray-400 mt-1">
            두 버전 중 하나를 선택해줘.
          </p>
        </header>

        {/* 가사 옵션 */}
        <section className="grid gap-4 md:grid-cols-2">
          {options.map((opt) => {
            const active = selected === opt.id;
            return (
              <button
                key={opt.id}
                type="button"
                onClick={() => !isSubmitting && setSelected(opt.id)}
                className={`rounded-2xl border p-4 text-left transition
                  ${
                    active
                      ? "border-cyan-500/70 bg-cyan-500/10"
                      : "border-gray-800 bg-[#0f0f14]"
                  }`}
              >
                <div className="flex justify-between items-center mb-2">
                  <span className="text-gray-200">Version {opt.id}</span>
                  {active && <Check className="w-4 h-4 text-cyan-400" />}
                </div>

                <div className="h-[420px] overflow-auto rounded-xl bg-black/40 p-3">
                  <pre className="whitespace-pre-wrap text-gray-200 text-sm">
                    {opt.text}
                  </pre>
                </div>
              </button>
            );
          })}
        </section>

        {/* Footer */}
        <section className="flex justify-between">
          <button
            onClick={handleBack}
            disabled={isSubmitting}
            className="h-12 px-4 rounded-xl border border-gray-700 text-gray-200"
          >
            <ArrowLeft className="inline w-4 h-4 mr-1" />
            Back
          </button>

          <button
            onClick={handleComplete}
            disabled={!canComplete}
            className="h-12 px-6 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 text-white"
          >
            <Sparkles className="inline w-4 h-4 mr-1" />
            Complete
          </button>
        </section>

        {errorMsg && (
          <p className="text-center text-red-400">{errorMsg}</p>
        )}
      </div>

      {/* Overlay */}
      {isSubmitting && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center">
          <div className="bg-[#121217] p-6 rounded-2xl w-[360px] space-y-4">
            <p className="text-white text-lg">Generating Video…</p>
            <p className="text-gray-400 text-sm">{steps[stepIndex]}</p>
            <div className="h-2 bg-black rounded">
              <div className="h-full w-2/3 bg-cyan-500 animate-pulse rounded" />
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
