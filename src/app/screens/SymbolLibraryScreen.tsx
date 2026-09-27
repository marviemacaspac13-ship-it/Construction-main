import { useEffect, useRef, useState } from "react";
import { Search, UploadCloud, Trash2, CheckCircle2, ImageOff, Loader2 } from "lucide-react";
import { SectionBar, Mono } from "../components/ui";
import { listMaterials, listTemplates, uploadTemplate, deleteTemplate, type MaterialCatalogItem, type TemplateLibrary } from "../../lib/templates";

export function SymbolLibraryScreen() {
  const [materials, setMaterials] = useState<MaterialCatalogItem[]>([]);
  const [templates, setTemplates] = useState<TemplateLibrary>({});
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [uploadingId, setUploadingId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [confirming, setConfirming] = useState<{ itemId: string; filename: string } | null>(null);
  const fileInputs = useRef<Record<string, HTMLInputElement | null>>({});

  const refresh = () => {
    Promise.all([listMaterials(), listTemplates()])
      .then(([m, t]) => { setMaterials(m); setTemplates(t); })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load."))
      .finally(() => setLoading(false));
  };

  useEffect(() => { refresh(); }, []);

  const handleUpload = async (itemId: string, file: File) => {
    setUploadingId(itemId);
    setError("");
    try {
      await uploadTemplate(itemId, file);
      refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed.");
    } finally {
      setUploadingId(null);
    }
  };

  // What removing one crop does to scanning, worst case first. Only the
  // electrical route prices from these crops (plumbing reads printed tags).
  // An item with no crop left is the dangerous case: its trade still has
  // references, so scans succeed - they just stop finding it and price lower.
  const deleteConsequence = (itemId: string): { severe: boolean; text: string } => {
    const category = materials.find((m) => m.item_id === itemId)?.category;
    if (category === "electrical") {
      const tradeLeft =
        materials
          .filter((m) => m.category === "electrical")
          .reduce((n, m) => n + (templates[m.item_id] ?? []).length, 0) - 1;
      if (tradeLeft === 0) {
        return { severe: true, text: "This is the last electrical crop. Every Electrical Plan scan will be refused until one is added." };
      }
      if ((templates[itemId] ?? []).length - 1 === 0) {
        return { severe: true, text: `${itemId} will no longer be detected on any plan. Estimates will come out lower, with no warning.` };
      }
    }
    return { severe: false, text: "The symbol library is shared, so this changes scans for every user." };
  };

  const handleDelete = async (itemId: string, filename: string) => {
    setConfirming(null);
    setTemplates((t) => ({ ...t, [itemId]: (t[itemId] ?? []).filter((f) => f !== filename) }));
    try {
      await deleteTemplate(itemId, filename);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Delete failed.");
      refresh();
    }
  };

  const filtered = materials.filter(
    (m) => m.item_name.toLowerCase().includes(search.toLowerCase()) || m.item_id.toLowerCase().includes(search.toLowerCase())
  );

  const withCount = filtered.filter((m) => (templates[m.item_id] ?? []).length > 0).length;

  return (
    <div className="p-10 max-w-4xl animate-page-in">
      <SectionBar>Symbol Library</SectionBar>

      <div className="border border-border rounded-lg p-6 bg-card mb-6">
        <p className="text-[12px] text-muted-foreground leading-relaxed">
          Upload one clean reference image per catalog item — a tight crop of exactly how that symbol looks on your
          plans. Matching works immediately after upload, no training required. You can upload more than one
          reference per item if the symbol is drawn slightly differently across your plan sets.
        </p>
      </div>

      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center h-9 border border-border rounded-lg px-3 gap-2 w-72 focus-within:border-foreground/25 transition-colors">
          <Search size={12} className="text-muted-foreground shrink-0" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search catalog item"
            className="bg-transparent text-[12px] font-mono text-foreground placeholder:text-muted-foreground/50 focus:outline-none flex-1"
          />
        </div>
        <Mono>{withCount}/{materials.length} items have a reference</Mono>
      </div>

      {error && <p className="text-[11px] font-mono text-red-400 mb-4 animate-pop-in">{error}</p>}

      {loading ? (
        <p className="text-[12px] font-mono text-muted-foreground flex items-center gap-2">
          <Loader2 size={12} className="animate-spin-slow" /> Loading catalog…
        </p>
      ) : (
        <div className="border border-border rounded-lg overflow-hidden">
          {filtered.map((m, i) => {
            const files = templates[m.item_id] ?? [];
            return (
              <div
                key={m.item_id}
                className="flex items-center gap-4 px-5 py-4 border-b border-border last:border-0 hover:bg-accent/20 transition-colors animate-stagger"
                style={{ animationDelay: `${i * 30}ms` }}
              >
                <span className={`w-6 h-6 rounded-full border flex items-center justify-center shrink-0 ${files.length > 0 ? "border-emerald-700 text-emerald-400" : "border-border text-muted-foreground"}`}>
                  {files.length > 0 ? <CheckCircle2 size={13} /> : <ImageOff size={12} />}
                </span>

                <div className="w-40 shrink-0">
                  <p className="text-[12px] font-mono text-foreground truncate">{m.item_name}</p>
                  <p className="text-[10px] font-mono text-muted-foreground">{m.item_id} · {m.unit ?? "—"}</p>
                </div>

                <div className="flex items-center gap-2 flex-wrap flex-1">
                  {files.map((f) => (
                    <span key={f} className="flex items-center gap-1.5 px-2 py-1 border border-border rounded-md text-[10px] font-mono text-muted-foreground">
                      {f.slice(0, 10)}…
                      <button
                        onClick={() => setConfirming({ itemId: m.item_id, filename: f })}
                        title={`Delete ${f}`}
                        className="text-muted-foreground hover:text-red-400 press-scale"
                      >
                        <Trash2 size={10} />
                      </button>
                    </span>
                  ))}

                  {confirming?.itemId === m.item_id && (() => {
                    const consequence = deleteConsequence(m.item_id);
                    return (
                      <div className="basis-full mt-1 p-3 border border-red-900/50 rounded-md bg-red-950/10 animate-pop-in">
                        <p className="text-[10px] font-mono text-muted-foreground mb-1 leading-relaxed">
                          Delete <span className="text-foreground break-all">"{confirming.filename}"</span>? This can't be undone here.
                        </p>
                        <p className={`text-[10px] font-mono mb-3 leading-relaxed ${consequence.severe ? "text-orange-400" : "text-muted-foreground"}`}>
                          {consequence.text}
                        </p>
                        <div className="flex gap-1.5">
                          <button
                            onClick={() => handleDelete(confirming.itemId, confirming.filename)}
                            className="h-7 px-4 rounded border border-red-900/50 text-[10px] font-mono text-red-400 hover:bg-red-950 press-scale transition-colors"
                          >
                            Delete
                          </button>
                          <button
                            onClick={() => setConfirming(null)}
                            className="h-7 px-4 rounded border border-border text-[10px] font-mono text-muted-foreground hover:bg-accent press-scale transition-colors"
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    );
                  })()}
                </div>

                <button
                  onClick={() => fileInputs.current[m.item_id]?.click()}
                  disabled={uploadingId === m.item_id}
                  className="h-8 px-3 rounded-lg border border-border text-[10px] font-mono uppercase tracking-widest flex items-center gap-1.5 press-scale hover:bg-accent disabled:opacity-40 shrink-0"
                >
                  {uploadingId === m.item_id ? <Loader2 size={11} className="animate-spin-slow" /> : <UploadCloud size={11} />}
                  Add
                </button>
                <input
                  ref={(el) => { fileInputs.current[m.item_id] = el; }}
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={(e) => { const f = e.target.files?.[0]; if (f) handleUpload(m.item_id, f); e.target.value = ""; }}
                />
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
