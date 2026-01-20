"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Check,
  ArrowLeft,
  Sparkles,
  ChevronDown,
  ChevronUp,
  Clipboard,
} from "lucide-react";

const API_BASE = "";

/* =======================
   Types
======================= */

type LyricOption = {
  id: 1 | 2;              // UI용 (1/2)
  conceptId: string;      // ✅ 백에 보낼 selected_concept_id
  text: string;           // lyrics
  log?: string;           // qa 결과 stringified
};

type JobApi = {
  job_id: string;
  status:
    | "queued"
    | "running"
    | "completed"
    | "failed"
    | "hitl_required"
    | string;
  progress?: number | null;
  result?: {
    concepts?: Array<{ concept_id: string; lyrics: string; mv_script?: any }>;
    qa_results?: any[];
    selected_concept?: any;
  } | null;
  error?: string | null;
};

function qaToLog(qa: any): string {
  try {
    return JSON.stringify(qa, null, 2);
  } catch {
    return String(qa);
  }
}

async function fetchJob(jobId: string): Promise<JobApi> {
  const res = await fetch(`${API_BASE}/jobs/${jobId}`, { cache: "no-store" });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Failed to fetch /jobs/${jobId}`);
  }
  return res.json();
}

function extractOptionsFromJob(job: JobApi): LyricOption[] | null {
  const concepts = job.result?.concepts ?? [];
  if (concepts.length < 2) return null;

  const c1 = concepts[0];
  const c2 = concepts[1];
  if (!c1?.concept_id || !c2?.concept_id) return null;
  if (typeof c1.lyrics !== "string" || typeof c2.lyrics !== "string") return null;

  const qa = job.result?.qa_results ?? [];
  const log1 = qa[0] ? qaToLog(qa[0]) : undefined;
  const log2 = qa[1] ? qaToLog(qa[1]) : undefined;

  return [
    { id: 1, conceptId: String(c1.concept_id), text: c1.lyrics, log: log1 },
    { id: 2, conceptId: String(c2.concept_id), text: c2.lyrics, log: log2 },
  ];
}

/* =======================
   Page
======================= */

export default function LyricSelectionPage() {
  const router = useRouter();

  const [jobId, setJobId] = useState<string | null>(null);

  const [options, setOptions] = useState<LyricOption[]>([]);
  const [selected, setSelected] = useState<1 | 2 | null>(null);

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const [logOpen, setLogOpen] = useState<{ 1: boolean; 2: boolean }>({
    1: false,
    2: false,
  });

  const pollingRef = useRef<number | null>(null);
  const stopPolling = () => {
    if (pollingRef.current) {
      window.clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  };

  /* =======================
     Mount: options를 sessionStorage로 먼저 채우고
     없으면 /jobs/{job_id}에서 가져오기
  ======================= */

  useEffect(() => {
    const id = sessionStorage.getItem("job_id");
    setJobId(id);

    // ✅ sessionStorage 기반 (이전 페이지에서 저장했으면 빠르게 보여줌)
    const v1 = sessionStorage.getItem("lyrics_v1");
    const v2 = sessionStorage.getItem("lyrics_v2");
    const log1 = sessionStorage.getItem("lyrics_log1");
    const log2 = sessionStorage.getItem("lyrics_log2");
    const cid1 = sessionStorage.getItem("concept_id_1");
    const cid2 = sessionStorage.getItem("concept_id_2");

    if (id && v1 && v2 && cid1 && cid2) {
      setOptions([
        { id: 1, conceptId: cid1, text: v1, log: log1 ?? undefined },
        { id: 2, conceptId: cid2, text: v2, log: log2 ?? undefined },
      ]);
      return;
    }

    // fallback
    if (!id) {
      router.replace("/");
      return;
    }

    startFetchUntilOptions(id);

    return () => stopPolling();
  }, []);

  const startFetchUntilOptions = (id: string) => {
    if (pollingRef.current) return;

    pollingRef.current = window.setInterval(async () => {
      try {
        const job = await fetchJob(id);

        if (job.error || job.status === "failed") {
          throw new Error(job.error || "Job failed");
        }

        const extracted = extractOptionsFromJob(job);
        if (extracted) {
          setOptions(extracted);

          // ✅ 재진입 대비 저장 (conceptId 포함)
          sessionStorage.setItem("job_id", job.job_id);
          sessionStorage.setItem("lyrics_v1", extracted[0].text);
          sessionStorage.setItem("lyrics_v2", extracted[1].text);
          sessionStorage.setItem("concept_id_1", extracted[0].conceptId);
          sessionStorage.setItem("concept_id_2", extracted[1].conceptId);
          if (extracted[0].log) sessionStorage.setItem("lyrics_log1", extracted[0].log);
          if (extracted[1].log) sessionStorage.setItem("lyrics_log2", extracted[1].log);

          stopPolling();
        }
      } catch (e) {
        console.error(e);
        stopPolling();
        setErrorMsg("가사를 불러오지 못했어요. 다시 시도해줘.");
      }
    }, 1000);
  };

  /* =======================
     UI Handlers
  ======================= */

  const canComplete = selected !== null && !isSubmitting;

  const handleBack = () => {
    if (isSubmitting) return;
    router.back();
  };

  const toggleLog = (id: 1 | 2) => {
    setLogOpen((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const copyToClipboard = async (text?: string) => {
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
    } catch (e) {
      console.error("Clipboard copy failed", e);
    }
  };

  /* =======================
     Complete → POST /jobs/{job_id}/hitl
  ======================= */

  const steps = useMemo(
    () => [
      "선택한 컨셉으로 진행하는 중…",
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
    const t = window.setInterval(() => {
      setStepIndex((p) => (p + 1) % steps.length);
    }, 7000);
    return () => window.clearInterval(t);
  }, [isSubmitting, steps.length]);

  const handleComplete = async () => {
    if (!canComplete) return;

    const id = jobId ?? sessionStorage.getItem("job_id");
    if (!id) {
      setErrorMsg("job_id가 없어요. 처음부터 다시 시도해줘.");
      return;
    }

    const chosen = options.find((o) => o.id === selected);
    if (!chosen) {
      setErrorMsg("선택한 버전을 찾지 못했어요.");
      return;
    }

    setIsSubmitting(true);
    setErrorMsg(null);

    try {
      const res = await fetch(`${API_BASE}/jobs/${id}/hitl`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          job_id: id,
          selected_concept_id: chosen.conceptId,
        }),
      });

      if (!res.ok) {
        const text = await res.text().catch(() => "");
        throw new Error(text || "HITL submit failed");
      }

      // ✅ 지금은 데모상 result로 이동
      // 나중에는 여기서 /jobs/{id} polling 해서 video_url 나오면 result로.
      router.push("/result");
    } catch (err: any) {
      console.error(err);
      setErrorMsg(err?.message ?? "Request failed");
      setIsSubmitting(false);
    }
  };

  /* =======================
     Render
  ======================= */

  const ready = options.length >= 2;

  return (
    <main className="min-h-screen bg-[#0b0b0f]">
      <div className="mx-auto max-w-4xl px-4 py-12 space-y-8">
        <header className="space-y-2">
          <h1 className="text-3xl text-white">Lyrics Selection</h1>
          <p className="text-gray-400">
            두 버전 중 하나를 선택해줘. (필요하면 로그도 확인 가능)
          </p>
          {jobId && <p className="text-xs text-gray-600">job_id: {jobId}</p>}
        </header>

        {!ready ? (
          <div className="rounded-2xl border border-gray-800 bg-[#0f0f14] p-6">
            <p className="text-gray-300">가사를 불러오는 중...</p>
            <p className="text-gray-500 text-sm mt-2">
              잠시만 기다려줘.
            </p>
          </div>
        ) : (
          <section className="grid gap-4 md:grid-cols-2">
            {options.map((opt) => {
              const active = selected === opt.id;
              const hasLog = Boolean(opt.log && opt.log.trim().length > 0);

              return (
                <div
                  key={opt.id}
                  className={[
                    "rounded-2xl border p-4 transition",
                    active
                      ? "border-cyan-500/70 bg-cyan-500/10"
                      : "border-gray-800 bg-[#0f0f14]",
                  ].join(" ")}
                >
                  <button
                    type="button"
                    onClick={() => !isSubmitting && setSelected(opt.id)}
                    className="w-full text-left"
                  >
                    <div className="flex justify-between items-center mb-2">
                      <span className="text-gray-200 font-medium">
                        Version {opt.id}
                      </span>
                      {active && <Check className="w-4 h-4 text-cyan-400" />}
                    </div>

                    <div className="h-[360px] overflow-auto rounded-xl bg-black/40 p-3 border border-gray-800">
                      <pre className="whitespace-pre-wrap text-gray-200 text-sm leading-6">
                        {opt.text}
                      </pre>
                    </div>

                    <p className="mt-2 text-xs text-gray-600">
                      concept_id: {opt.conceptId}
                    </p>
                  </button>

                  <div className="mt-3 flex items-center justify-between gap-2">
                    <button
                      type="button"
                      onClick={() => toggleLog(opt.id)}
                      disabled={!hasLog}
                      className={[
                        "h-10 px-3 rounded-xl border text-sm inline-flex items-center gap-2 transition",
                        hasLog
                          ? "border-gray-800 bg-[#121217] text-gray-200 hover:bg-[#14141a]"
                          : "border-gray-900 bg-[#0f0f14] text-gray-600 cursor-not-allowed",
                      ].join(" ")}
                    >
                      {logOpen[opt.id] ? (
                        <>
                          <ChevronUp className="w-4 h-4" />
                          로그 숨기기
                        </>
                      ) : (
                        <>
                          <ChevronDown className="w-4 h-4" />
                          로그 보기
                        </>
                      )}
                    </button>

                    <button
                      type="button"
                      onClick={() => copyToClipboard(opt.log)}
                      disabled={!hasLog}
                      className={[
                        "h-10 px-3 rounded-xl border text-sm inline-flex items-center gap-2 transition",
                        hasLog
                          ? "border-gray-800 bg-[#121217] text-gray-200 hover:bg-[#14141a]"
                          : "border-gray-900 bg-[#0f0f14] text-gray-600 cursor-not-allowed",
                      ].join(" ")}
                      title="로그 복사"
                    >
                      <Clipboard className="w-4 h-4" />
                      Copy
                    </button>
                  </div>

                  {hasLog && logOpen[opt.id] && (
                    <div className="mt-3 rounded-xl border border-gray-800 bg-black/30 p-3">
                      <p className="text-xs text-gray-400 mb-2">
                        QA / Log (Version {opt.id})
                      </p>
                      <pre className="whitespace-pre-wrap text-xs leading-5 text-gray-200 max-h-[220px] overflow-auto">
                        {opt.log}
                      </pre>
                    </div>
                  )}
                </div>
              );
            })}
          </section>
        )}

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
            className="h-12 px-6 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 text-white disabled:opacity-50"
          >
            <Sparkles className="inline w-4 h-4 mr-1" />
            Complete
          </button>
        </section>

        {errorMsg && <p className="text-center text-red-400">{errorMsg}</p>}
      </div>

      {isSubmitting && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center px-4">
          <div className="bg-[#121217] p-6 rounded-2xl w-[360px] space-y-4 border border-gray-800">
            <p className="text-white text-lg font-medium">Processing…</p>
            <p className="text-gray-400 text-sm">{steps[stepIndex]}</p>
            <div className="h-2 bg-black rounded overflow-hidden border border-gray-800">
              <div className="h-full w-2/3 bg-cyan-500 animate-pulse rounded" />
            </div>
            <p className="text-xs text-gray-500">
              선택한 버전을 백엔드에 전달하는 중이에요.
            </p>
          </div>
        </div>
      )}
    </main>
  );
}
