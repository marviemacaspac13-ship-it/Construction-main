import { useState } from "react";
import { MessageSquare, Check, Send, Heart } from "lucide-react";
import { SectionBar, Btn, FieldWrap, TxtInput, TxtArea } from "../components/ui";

export function FeedbackScreen() {
  const [email, setEmail]           = useState("");
  const [title, setTitle]           = useState("");
  const [desc, setDesc]             = useState("");
  const [categories, setCategories] = useState<string[]>([]);
  const [sent, setSent]             = useState(false);

  const chips  = ["Bug Report", "Feature Request", "General Feedback", "Performance"];
  const toggle = (t: string) =>
    setCategories((prev) => prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t]);

  return (
    <div className="p-10 max-w-3xl animate-page-in">
      <SectionBar>Feedback</SectionBar>

      <div className="border border-border rounded-lg bg-card overflow-hidden">
        <div className="flex">
          <div className="flex-1 p-6 space-y-5">
            <div className="flex items-center gap-3 pb-5 border-b border-border">
              <div className="w-8 h-8 border border-border rounded-lg flex items-center justify-center text-muted-foreground">
                <MessageSquare size={13} />
              </div>
              <div>
                <p className="text-[12px] font-mono font-semibold text-foreground">Submit Feedback</p>
                <p className="text-[10px] font-mono text-muted-foreground">Let us know how we can improve TRACE.</p>
              </div>
            </div>

            <FieldWrap label="Email">
              <TxtInput type="email" value={email} onChange={setEmail} placeholder="your@email.com" />
            </FieldWrap>

            <FieldWrap label="Title">
              <TxtInput value={title} onChange={setTitle} placeholder="Brief summary of your feedback" />
            </FieldWrap>

            <FieldWrap label="Category">
              <div className="flex flex-wrap gap-1.5">
                {chips.map((c) => (
                  <button
                    key={c}
                    onClick={() => toggle(c)}
                    className={`flex items-center gap-1.5 h-6 px-2.5 border rounded text-[10px] font-mono transition-colors ${
                      categories.includes(c) ? "border-foreground/40 text-foreground bg-accent" : "border-border text-muted-foreground hover:border-foreground/25"
                    }`}
                  >
                    <div className={`w-2.5 h-2.5 rounded-sm border flex items-center justify-center shrink-0 ${categories.includes(c) ? "border-foreground bg-foreground" : "border-muted-foreground"}`}>
                      {categories.includes(c) && <Check size={7} className="text-background" />}
                    </div>
                    {c}
                  </button>
                ))}
              </div>
            </FieldWrap>

            <FieldWrap label="Description">
              <TxtArea value={desc} onChange={setDesc} placeholder="Describe your feedback in detail..." rows={4} maxLength={250} />
              <p className="text-[9px] font-mono text-muted-foreground/40 text-right mt-1">{desc.length}/250</p>
            </FieldWrap>

            {sent ? (
              <div className="flex items-center gap-2 text-[11px] font-mono text-foreground">
                <div className="w-5 h-5 rounded-full border border-foreground flex items-center justify-center">
                  <Check size={9} />
                </div>
                Feedback sent — thank you.
              </div>
            ) : (
              <Btn variant="secondary" onClick={() => setSent(true)} icon={<Send size={11} />}>Submit</Btn>
            )}
          </div>

          {/* Heart illustration */}
          <div className="w-44 shrink-0 flex items-center justify-center border-l border-border bg-background">
            <div className="relative flex items-center justify-center w-32 h-32">
              {[0, 1, 2, 3, 4].map((i) => (
                <div
                  key={i}
                  className="absolute border border-foreground/[0.07]"
                  style={{ width: `${(i + 1) * 24}px`, height: `${(i + 1) * 24}px`, borderRadius: "3px", transform: "rotate(45deg)" }}
                />
              ))}
              <div className="relative z-10 w-12 h-12 border border-foreground/20 flex items-center justify-center" style={{ borderRadius: "3px", transform: "rotate(45deg)" }}>
                <Heart size={18} className="text-foreground/40" style={{ transform: "rotate(-45deg)" }} />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
