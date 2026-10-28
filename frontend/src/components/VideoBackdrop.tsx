import { useEffect, useRef } from "react";

/** Muted looping video backdrop with a high-readability veil.
 *  Decorative: hidden from the accessibility tree, pointer-events-none.
 *  The poster acts as the fallback. */
export function VideoBackdrop({ src, poster }: { src: string; poster?: string }) {
  const ref = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const v = ref.current;
    if (!v) return;
    v.defaultMuted = true;
    v.muted = true;
    // Explicit play() to overcome modern browser autoplay restrictions
    v.play().catch(() => {
      // Autoplay silently handled if blocked by browser policy
    });
    if (typeof window !== "undefined" && window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      v.pause();
    }
  }, [src]);

  return (
    <div className="vid-backdrop absolute inset-0 overflow-hidden pointer-events-none z-0" aria-hidden="true">
      <video
        ref={ref}
        className="h-full w-full object-cover"
        src={src}
        poster={poster}
        autoPlay
        loop
        muted
        playsInline
      >
        <source src={src} type="video/mp4" />
      </video>
      {/* Precision overlay veil ensuring crisp contrast for foreground cards */}
      <div className="absolute inset-0 bg-gradient-to-br from-slate-950/85 via-slate-950/45 to-slate-950/90" />
      <div className="absolute inset-0 bg-[radial-gradient(900px_500px_at_12%_-10%,rgba(6,182,212,0.18),transparent_60%),radial-gradient(800px_500px_at_100%_10%,rgba(16,185,129,0.15),transparent_60%)]" />
    </div>
  );
}

export default VideoBackdrop;
