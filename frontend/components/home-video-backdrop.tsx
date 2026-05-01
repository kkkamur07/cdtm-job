"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";

const VIDEO_SRC = "/video-background.mp4";

/**
 * Full-viewport background for `/` only. Loads MP4 after idle so first paint stays fast.
 */
export function HomeVideoBackdrop() {
  const pathname = usePathname();
  const videoRef = useRef<HTMLVideoElement>(null);
  const [loadVideo, setLoadVideo] = useState(false);

  useEffect(() => {
    if (pathname !== "/") return;

    let cancelled = false;
    const run = () => {
      if (!cancelled) setLoadVideo(true);
    };

    let idleId: number | undefined;
    let timeoutId: number | undefined;

    if (typeof window.requestIdleCallback === "function") {
      idleId = window.requestIdleCallback(run, { timeout: 2500 });
    } else {
      timeoutId = window.setTimeout(run, 300) as unknown as number;
    }

    return () => {
      cancelled = true;
      if (idleId !== undefined) {
        window.cancelIdleCallback(idleId);
      }
      if (timeoutId !== undefined) {
        window.clearTimeout(timeoutId);
      }
    };
  }, [pathname]);

  useEffect(() => {
    const el = videoRef.current;
    if (!el || !loadVideo || pathname !== "/") return;
    void el.play().catch(() => {});
  }, [loadVideo, pathname]);

  if (pathname !== "/") return null;

  return (
    <div
      className="pointer-events-none fixed inset-0 z-0 h-[100dvh] w-full overflow-hidden"
      aria-hidden
    >
      <div className="absolute inset-0 hidden bg-gradient-to-br from-zinc-900 via-cdtm to-zinc-950 motion-reduce:block" />

      {loadVideo && (
        <video
          ref={videoRef}
          autoPlay
          muted
          loop
          playsInline
          preload="none"
          className="absolute inset-0 h-full w-full object-cover motion-reduce:hidden"
        >
          <source src={VIDEO_SRC} type="video/mp4" />
        </video>
      )}

      <div className="absolute inset-0 bg-gradient-to-b from-black/60 via-black/45 to-black/80 motion-reduce:hidden" />
      <div className="absolute inset-0 bg-gradient-to-t from-zinc-950/95 via-transparent to-black/35 motion-reduce:hidden" />
    </div>
  );
}
