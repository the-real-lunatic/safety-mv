"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Check, ArrowLeft, Sparkles } from "lucide-react";

type LyricOption = {
  id: 1 | 2;        // 버전 번호
  text: string;     // 백에서 생성한 텍스트
};

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

export default function LyricSelectionPage() {
  const router = useRouter();

  // TODO: 실제로는 /get_lyrics 같은 API로 받아오거나,
  // post_job 응답에서 받은 job_id로 조회해서 가져오면 됨.
  const [options, setOptions] = useState<LyricOption[]>([
    { id: 1, text: "Version 1 lyrics...\n(placeholder)\n\n여기에 백에서 생성한 텍스트" },
    { id: 2, text: "Version 2 lyrics...\n(placeholder)\n\n여기에 백에서 생성한 텍스트" },
  ]);

  const [selected, setSelected] = useState<1 | 2 | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // 지루함 방지용 "단계 메시지"
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
  const intervalRef = useRef<number | null>(null);

  useEffect(() => {
    if (!isSubmitting) {
      if (intervalRef.current) window.clearInterval(intervalRef.current);
      intervalRef.current = null;
      setStepIndex(0);
      return;
    }

    // 1분 동안 너무 정직하게 퍼센트 보여주기보다,
    // “느낌상 진행되는” 단계 메시지로 지루함 완화
    intervalRef.current = window.setInterval(() => {
      setStepIndex((prev) => (prev + 1) % steps.length);
    }, 7000);

    return () => {
      if (intervalRef.current) window.clearInterval(intervalRef.current);
      intervalRef.current = null;
    };
  }, [isSubmitting, steps.length]);

  const canComplete = selected !== null && !isSubmitting;

  const handleBack = () => {
    if (isSubmitting) return;
    router.back();
  };

const MOCK_MODE = true; // 백 붙이면 false로

const handleComplete = async () => {
  if (!canComplete) return;

  setIsSubmitting(true);
  setErrorMsg(null);

  try {
    console.log("Posting selected version:", selected);

    if (!MOCK_MODE) {
      const res = await fetch("/post_version", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ version: selected }),
      });

      if (!res.ok) {
        const text = await res.text().catch(() => "");
        throw new Error(text || `POST /post_version failed (${res.status})`);
      }

      // 백 붙인 뒤에는 여기서 polling 하거나 완료 이벤트 받으면 됨
      await sleep(60_000);
    } else {
      // ✅ 백 없이 “생성중 이펙트”만 보여주기
      await sleep(6_000); // 5~10초 아무거나
    }

    router.push("/result");
  } catch (err: any) {
    setErrorMsg(err?.message ?? "Request failed");
    setIsSubmitting(false);
  }
};


//   const handleComplete = async () => {
//     if (!canComplete) return;

//     setIsSubmitting(true);
//     setErrorMsg(null);

//     try {
//         console.log("Posting selected version:", selected);
//       const res = await fetch("/post_version", {
//         method: "POST",
//         headers: { "Content-Type": "application/json" },
//         body: JSON.stringify({ version: selected }),
//       });

//       if (!res.ok) {
//         const text = await res.text().catch(() => "");
//         throw new Error(text || `POST /post_version failed (${res.status})`);
//       }

//       // ✅ 지금은 1분 정도 걸린다고 했으니 임시로 delay.
//       // 나중엔 여기서:
//       // - polling으로 완료 체크
//       // - 또는 SSE/WebSocket으로 완료 이벤트를 받으면
//       // router.push("/result") 같은 다음 화면으로 이동하면 됨.
//       await sleep(60_000);

//       router.push("/result"); // 원하는 다음 페이지로 바꿔줘
//     } catch (err: any) {
//       setErrorMsg(err?.message ?? "Request failed");
//       setIsSubmitting(false);
//     //   !todo 일단 넘어감. 백 연결 후 삭제
//         await sleep(5_000);
//         router.push("/result");
//     }
//   };

  return (
    <main className="min-h-screen bg-[#0b0b0f]">
      <div className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-10 py-10 sm:py-14 lg:py-16">
        <div className="rounded-3xl border border-gray-800/60 bg-[#0f0f14]/60 backdrop-blur px-5 sm:px-8 py-7 sm:py-10 shadow-xl shadow-black/30 space-y-8">
          {/* Header */}
          <header className="space-y-2">
            <h1 className="text-2xl md:text-3xl text-white tracking-tight">
              Lyrics Selection
            </h1>
            <p className="text-gray-400 text-sm md:text-base">
              두 버전 중 하나를 선택해줘. 선택한 버전으로 영상이 생성돼.
            </p>
          </header>

          {/* Options */}
          <section className="grid gap-4 md:grid-cols-2">
            {options.map((opt) => {
              const active = selected === opt.id;
              return (
                <button
                  key={opt.id}
                  type="button"
                  onClick={() => !isSubmitting && setSelected(opt.id)}
                  className={[
                    "text-left rounded-2xl border p-4 transition-all",
                    "focus:outline-none focus:ring-2 focus:ring-cyan-500/20",
                    active
                      ? "border-cyan-500/70 bg-cyan-500/10"
                      : "border-gray-800 bg-[#0f0f14] hover:border-gray-700 hover:bg-[#14141a]",
                    isSubmitting ? "opacity-70 cursor-not-allowed" : "",
                  ].join(" ")}
                >
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-gray-200 text-sm font-medium">
                      Version {opt.id}
                    </span>
                    <span
                      className={[
                        "inline-flex h-7 w-7 items-center justify-center rounded-lg border",
                        active
                          ? "border-cyan-500/40 bg-cyan-500/15 text-cyan-200"
                          : "border-gray-800 bg-transparent text-gray-600",
                      ].join(" ")}
                    >
                      {active ? <Check className="h-4 w-4" /> : null}
                    </span>
                  </div>

                  {/* 세로로 긴 텍스트 박스 */}
                  <div className="h-[420px] overflow-auto rounded-xl bg-[#0b0b0f] border border-gray-800 px-4 py-3">
                    <pre className="whitespace-pre-wrap text-sm leading-6 text-gray-200">
                      {opt.text}
                    </pre>
                  </div>

                  <p className="mt-3 text-xs text-gray-500">
                    클릭해서 선택 (둘 중 1개만)
                  </p>
                </button>
              );
            })}
          </section>

          {/* Footer Buttons */}
          <section className="flex items-center justify-between gap-3">
            <button
              type="button"
              onClick={handleBack}
              disabled={isSubmitting}
              className={[
                "h-12 px-4 rounded-2xl border",
                "border-gray-800 bg-[#0f0f14] text-gray-200",
                "hover:border-gray-700 hover:bg-[#14141a] transition-all",
                "disabled:opacity-50 disabled:cursor-not-allowed",
                "flex items-center justify-center gap-2",
              ].join(" ")}
            >
              <ArrowLeft className="w-4 h-4" />
              Back
            </button>

            <button
              type="button"
              onClick={handleComplete}
              disabled={!canComplete}
              className={[
                "h-12 px-5 rounded-2xl text-white",
                "bg-gradient-to-r from-cyan-500 to-blue-600",
                "hover:from-cyan-400 hover:to-blue-500",
                "shadow-lg shadow-cyan-500/15 hover:shadow-cyan-500/25 transition-all",
                "disabled:opacity-50 disabled:cursor-not-allowed",
                "flex items-center justify-center gap-2",
              ].join(" ")}
            >
              <Sparkles className="w-4 h-4" />
              Complete
            </button>
          </section>

          {errorMsg && (
            <p className="text-center text-sm text-red-400">{errorMsg}</p>
          )}
        </div>
      </div>

      {/* Generating Overlay (지루함 방지) */}
      {isSubmitting && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center px-4">
          <div className="w-full max-w-md rounded-3xl border border-gray-800/70 bg-[#121217] p-6 shadow-xl">
            <div className="flex items-center gap-3">
              <span className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-500/20">
                <Sparkles className="w-5 h-5 text-white" />
              </span>
              <div>
                <p className="text-white text-lg font-medium">
                  Generating Video…
                </p>
                <p className="text-gray-400 text-sm mt-0.5">
                  약 1분 정도 걸릴 수 있어요.
                </p>
              </div>
            </div>

            <div className="mt-5 space-y-3">
              <p className="text-gray-200 text-sm">
                {steps[stepIndex]}
              </p>

              {/* “느낌상” 진행바 */}
              <div className="h-2 w-full rounded-full bg-[#0f0f14] border border-gray-800 overflow-hidden">
                <div className="h-full w-2/3 bg-gradient-to-r from-cyan-500 to-blue-600 animate-pulse" />
              </div>

              <p className="text-gray-500 text-xs">
                팁: PRO 모드로 업그레이드하면 더 빠르게 고화질 영상 생성이 가능해요!
              </p>
            </div>

            {/* 지금은 취소 버튼 막는 게 안전(서버 job 취소 지원 전) */}
            <button
              type="button"
              disabled
              className="mt-6 w-full h-12 rounded-2xl border border-gray-800 bg-[#0f0f14] text-gray-500 cursor-not-allowed"
            >
              Rendering…
            </button>
          </div>
        </div>
      )}
    </main>
  );
}
