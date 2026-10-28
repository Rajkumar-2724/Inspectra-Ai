import { useEffect, useState } from "react";
import { Api } from "../services/api";

/** <img> tags cannot send the JWT header, so images are fetched as blobs and shown via object URLs. */
export function useAuthImage(id: number | undefined, kind: string, enabled = true) {
  const [url, setUrl] = useState<string | null>(null);
  const [missing, setMissing] = useState(false);
  useEffect(() => {
    if (!id || !enabled) return;
    let alive = true, obj: string | null = null;
    setUrl(null); setMissing(false);
    Api.imageBlob(id, kind).then((b) => { if (alive) { obj = URL.createObjectURL(b); setUrl(obj); } }).catch(() => alive && setMissing(true));
    return () => { alive = false; if (obj) URL.revokeObjectURL(obj); };
  }, [id, kind, enabled]);
  return { url, missing };
}
