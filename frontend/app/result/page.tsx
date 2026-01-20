"use client";

import { useEffect, useState } from "react";

export default function ResultPage() {
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    setUrl(sessionStorage.getItem("preview_url"));
  }, []);

  return (
    <main className="min-h-screen bg-[#0b0b0f] text-white">
      <div className="mx-auto max-w-4xl px-4 py-10 space-y-6">
        <h1 className="text-3xl font-semibold">Result</h1>

        {!url ? (
          <p className="text-gray-400">프리뷰 생성 오류</p>
        ) : (
          <div className="rounded-3xl border border-gray-800 bg-[#0f0f14] p-4">
            <video
              src={url}
              controls
              playsInline
              className="w-full rounded-2xl"
            />
            <div className="mt-3 flex gap-2">
              <a
                href={url}
                target="_blank"
                rel="noreferrer"
                className="px-4 h-11 inline-flex items-center rounded-2xl border border-gray-800 bg-[#121217] text-gray-200 hover:bg-[#14141a]"
              >
                Open file
              </a>
              <a
                href={url}
                download
                className="px-4 h-11 inline-flex items-center rounded-2xl bg-gradient-to-r from-cyan-500 to-blue-600 text-white"
              >
                Download
              </a>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
