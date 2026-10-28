import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { Api } from "../services/api";

export function ProductSelect({ value, onChange, id = "product" }: { value: number | ""; onChange: (v: number | "") => void; id?: string }) {
  const q = useQuery({ queryKey: ["products"], queryFn: () => Api.products() });

  // Automatically select the supported, ready product if current selection is empty or unsupported
  useEffect(() => {
    if (!q.data?.length) return;
    const current = q.data.find((p) => p.id === value);
    if (!current || !current.real_mode_ready) {
      const readyProd = q.data.find((p) => p.real_mode_ready);
      if (readyProd) {
        onChange(readyProd.id);
      }
    }
  }, [q.data, value, onChange]);

  return (
    <select id={id} className="input" value={value} onChange={(e) => onChange(e.target.value ? Number(e.target.value) : "")} aria-label="Product type">
      <option value="" disabled>Select target product…</option>
      {q.data?.map((p) => (
        <option key={p.id} value={p.id} disabled={!p.real_mode_ready}>
          {p.name} ({p.category}) {p.real_mode_ready ? "— [AI Model Active]" : "— (Unsupported / No Model)"}
        </option>
      ))}
    </select>
  );
}
