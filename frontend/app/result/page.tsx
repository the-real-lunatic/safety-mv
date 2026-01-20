"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, RefreshCw, Download, ExternalLink, Video } from "lucide-react";

export default function ResultPage() {
  const router = useRouter();
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    // lyricselection에서 저장한 키: video_url
    // 혹시 예전 코드/백에서 preview_url로 쓰는 경우도 대비
    const u =
      sessionStorage.getItem("video_url") ||
      sessionStorage.getItem("preview_url");

    setUrl(u);
  }, []);

  const filename = useMemo(() => {
    if (!url) return "video.mp4";
    const last = url.split("/").pop();
    return last && last.includes(".") ? last : "video.mp4";
  }, [url]);

  return (
    <main className="min-h-screen bg-[#0b0b0f] text-white">
      <div className="mx-auto max-w-4xl px-4 py-10 space-y-6">
        {/* Header */}
        <header className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-500/20">
              <Video className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-3xl font-semibold">Result</h1>
              <p className="text-gray-400 text-sm mt-1">
                생성된 영상을 확인하고 다운로드할 수 있어요.
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={() => router.back()}
            className="h-11 px-4 rounded-2xl border border-gray-800 bg-[#0f0f14] text-gray-200 hover:bg-[#14141a] transition-all inline-flex items-center gap-2"
          >
            <ArrowLeft className="w-4 h-4" />
            Back
          </button>
        </header>

        {!url ? (
          <div className="rounded-3xl border border-gray-800 bg-[#0f0f14] p-6 space-y-4">
            <p className="text-gray-300 text-lg">프리뷰 URL이 없어요.</p>
            <p className="text-gray-500 text-sm">
              렌더링이 실패했거나, 새로고침/직접 진입으로 인해 세션 값이 사라졌을 수 있어요.
            </p>

            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => router.push("/")}
                className="h-11 px-4 rounded-2xl bg-gradient-to-r from-cyan-500 to-blue-600 text-white inline-flex items-center gap-2"
              >
                <RefreshCw className="w-4 h-4" />
                Start Over
              </button>
              <button
                type="button"
                onClick={() => router.back()}
                className="h-11 px-4 rounded-2xl border border-gray-800 bg-[#121217] text-gray-200 hover:bg-[#14141a] inline-flex items-center gap-2"
              >
                <ArrowLeft className="w-4 h-4" />
                Go Back
              </button>
            </div>
          </div>
        ) : (
          <div className="rounded-3xl border border-gray-800 bg-[#0f0f14] p-4 space-y-4">
            <video
              src={url}
              controls
              playsInline
              className="w-full rounded-2xl border border-gray-800"
            />

            <div className="flex flex-wrap gap-2">
              <a
                href={url}
                target="_blank"
                rel="noreferrer"
                className="h-11 px-4 inline-flex items-center gap-2 rounded-2xl border border-gray-800 bg-[#121217] text-gray-200 hover:bg-[#14141a]"
              >
                <ExternalLink className="w-4 h-4" />
                Open file
              </a>

              <a
                href={url}
                download={filename}
                className="h-11 px-4 inline-flex items-center gap-2 rounded-2xl bg-gradient-to-r from-cyan-500 to-blue-600 text-white"
              >
                <Download className="w-4 h-4" />
                Download
              </a>

              <button
                type="button"
                onClick={() => router.push("/")}
                className="h-11 px-4 inline-flex items-center gap-2 rounded-2xl border border-gray-800 bg-[#121217] text-gray-200 hover:bg-[#14141a]"
              >
                <RefreshCw className="w-4 h-4" />
                Make another
              </button>
            </div>

            <p className="text-xs text-gray-600 break-all">
              Source: {url}
            </p>
          </div>
        )}
      </div>
    </main>
  );
}
