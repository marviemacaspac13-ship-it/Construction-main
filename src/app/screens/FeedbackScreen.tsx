import { useState } from "react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router";
import {
  MessageSquare,
  Check,
  Send,
  Heart,
  Bug,
  Sparkles,
  Gauge,
  Clock,
  LifeBuoy,
  ArrowUpRight,
  RotateCcw,
} from "lucide-react";
import { SectionBar, Mono, Btn, FieldWrap, TxtInput, TxtArea } from "../components/ui";

const CATEGORIES: { id: string; Icon: typeof Bug; desc: string }[] = [
  { id: "Bug Report",        Icon: Bug,           desc: "Something's not working" },
  { id: "Feature Request",   Icon: Sparkles,      desc: "An idea worth building" },
  { id: "General Feedback",  Icon: MessageSquare, desc: "Thoughts, praise, gripes" },
  { id: "Performance",       Icon: Gauge,         desc: "Slow or unresponsive" },
];

function IconBox({ children }: { children: ReactNode }) {
  return (
    <span className="w-9 h-9 rounded-lg border border-border bg-accent flex items-center justify-center text-foreground shrink-0">
      {children}
    </span>
  );
}

function AsideCard({ children, delay = 0 }: { children: ReactNode; delay?: number }) {
  return (
    <div className="border border-border rounded-lg bg-card p-5 hover-lift animate-stagger" style={{ animationDelay: `${delay}ms` }}>
      {children}
    </div>
  );
}

export function FeedbackScreen() {
  const navigate = useNavigate();
  const [email, setEmail]           = useState("");
  const [title, setTitle]           = useState("");
  const [desc, setDesc]             = useState("");
  const [categories, setCategories] = useState<string[]>([]);
  const [sent, setSent]             = useState(false);

  const toggle = (t: string) =>
    setCategories((prev) => (prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t]));

  const canSubmit = title.trim().length > 0 && desc.trim().length > 0;

  const resetForm = () => {
    setEmail(""); setTitle(""); setDesc(""); setCategories([]); setSent(false);
  };

  return (
    <div className="h-full flex flex-col p-10 animate-page-in">
      <SectionBar>Feedback</SectionBar>

      <div className="flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-[1fr_300px] gap-4">
        {/* Main form card */}
        <div className="border border-border rounded-lg bg-card overflow-hidden flex flex-col min-h-0">
          <div className="flex items-center gap-3 px-6 py-5 border-b border-border shrink-0">
            <IconBox><MessageSquare size={14} /></IconBox>
            <div>
              <p className="text-[12px] font-mono font-semibold text-foreground">Submit Feedback</p>
              <p className="text-[10px] font-mono text-muted-foreground">Let us know how we can improve TRACE.</p>
            </div>
          </div>

          {sent ? (
            <div className="flex-1 flex flex-col items-center justify-center gap-4 px-6 animate-pop-in">
              <div className="w-14 h-14 rounded-full border border-foreground/30 flex items-center justify-center">
                <Check size={20} className="text-foreground" />
              </div>
              <div className="text-center">
                <p className="text-[13px] font-mono font-semibold text-foreground mb-1">Feedback sent — thank you.</p>
                <p className="text-[10px] font-mono text-muted-foreground">We read every submission. Expect a reply at {email || "the address you provided"} if it needs one.</p>
              </div>
              <Btn variant="secondary" onClick={resetForm} icon={<RotateCcw size={11} />}>Submit another</Btn>
            </div>
          ) : (
            <>
              <div className="flex-1 min-h-0 overflow-y-auto px-6 py-5 space-y-5" style={{ scrollbarWidth: "none" }}>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <FieldWrap label="Email" hint="Optional — only if you'd like a reply">
                    <TxtInput type="email" value={email} onChange={setEmail} placeholder="your@email.com" />
                  </FieldWrap>
                  <FieldWrap label="Title">
                    <TxtInput value={title} onChange={setTitle} placeholder="Brief summary of your feedback" />
                  </FieldWrap>
                </div>

                <FieldWrap label="Category" hint="Select any that apply">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {CATEGORIES.map(({ id, Icon, desc: catDesc }) => {
                      const active = categories.includes(id);
                      return (
                        <button
                          key={id}
                          onClick={() => toggle(id)}
                          className={`flex items-center gap-3 px-3 py-2.5 border rounded-lg text-left transition-all press-scale ${
                            active ? "border-foreground/40 bg-accent" : "border-border hover:border-foreground/20 hover:bg-accent/40"
                          }`}
                        >
                          <span className={`w-7 h-7 rounded-lg border flex items-center justify-center shrink-0 transition-colors ${active ? "border-foreground/40 text-foreground bg-background" : "border-border text-muted-foreground"}`}>
                            <Icon size={13} />
                          </span>
                          <span className="min-w-0 flex-1">
                            <span className={`block text-[11px] font-mono ${active ? "text-foreground" : "text-muted-foreground"}`}>{id}</span>
                            <span className="block text-[9px] font-mono text-muted-foreground/60 truncate">{catDesc}</span>
                          </span>
                          <div className={`w-3.5 h-3.5 rounded-sm border flex items-center justify-center shrink-0 ${active ? "border-foreground bg-foreground" : "border-muted-foreground/40"}`}>
                            {active && <Check size={8} className="text-background" />}
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </FieldWrap>

                <FieldWrap label="Description">
                  <TxtArea value={desc} onChange={setDesc} placeholder="Describe your feedback in detail..." rows={4} maxLength={250} />
                  <p className="text-[9px] font-mono text-muted-foreground/40 text-right mt-1">{desc.length}/250</p>
                </FieldWrap>
              </div>

              <div className="flex items-center justify-between px-6 py-4 border-t border-border bg-background/40 shrink-0">
                <p className="text-[9px] font-mono text-muted-foreground/50">Fields marked required must be filled in.</p>
                <Btn
                  variant="primary"
                  onClick={() => canSubmit && setSent(true)}
                  icon={<Send size={11} />}
                  className={!canSubmit ? "opacity-40 cursor-not-allowed" : ""}
                >
                  Submit
                </Btn>
              </div>
            </>
          )}
        </div>

        {/* Aside rail */}
        <div className="flex flex-col gap-4 min-h-0 overflow-y-auto" style={{ scrollbarWidth: "none" }}>
          <AsideCard delay={0}>
            <div className="relative flex items-center justify-center w-full h-20 mb-4">
              {[0, 1, 2, 3].map((i) => (
                <div
                  key={i}
                  className="absolute border border-foreground/[0.08]"
                  style={{ width: `${(i + 1) * 20}px`, height: `${(i + 1) * 20}px`, borderRadius: "3px", transform: "rotate(45deg)" }}
                />
              ))}
              <div className="relative z-10 w-10 h-10 border border-foreground/25 bg-background flex items-center justify-center" style={{ borderRadius: "3px", transform: "rotate(45deg)" }}>
                <Heart size={16} className="text-foreground/50" style={{ transform: "rotate(-45deg)" }} />
              </div>
            </div>
            <p className="text-[11px] font-mono font-semibold text-foreground text-center mb-1">Every message read</p>
            <p className="text-[10px] font-mono text-muted-foreground text-center leading-relaxed">Our team reviews each submission personally — no auto-triage.</p>
          </AsideCard>

          <AsideCard delay={70}>
            <div className="flex items-center gap-3 mb-3">
              <IconBox><Clock size={14} /></IconBox>
              <Mono className="text-[10px]">Response Time</Mono>
            </div>
            <p className="text-[18px] font-mono font-bold text-foreground leading-none mb-1.5">24–48 hrs</p>
            <p className="text-[10px] font-mono text-muted-foreground">Typical turnaround for bug reports and urgent issues.</p>
          </AsideCard>

          <AsideCard delay={140}>
            <div className="flex items-center gap-3 mb-3">
              <IconBox><LifeBuoy size={14} /></IconBox>
              <Mono className="text-[10px]">Need It Faster?</Mono>
            </div>
            <p className="text-[10px] font-mono text-muted-foreground mb-4">Check the help center for guides and common fixes.</p>
            <button
              onClick={() => navigate("/help")}
              className="w-full flex items-center justify-between px-3 py-2 border border-border rounded-lg text-[10px] font-mono tracking-[0.1em] uppercase text-muted-foreground hover:text-foreground hover:bg-accent press-scale transition-colors"
            >
              Visit Help Center <ArrowUpRight size={11} />
            </button>
          </AsideCard>
        </div>
      </div>
    </div>
  );
}