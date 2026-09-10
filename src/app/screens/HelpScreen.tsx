import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { SectionBar, Mono } from "../components/ui";

export function HelpScreen() {
  const [open, setOpen] = useState<number | null>(null);

  const faqs = [
    { q: "What types of plans does TRACE support?",        a: "TRACE supports Floor Plans, Electrical Plans, and Plumbing Plans in PNG, JPG, and PDF formats." },
    { q: "Why is my estimate showing incorrect values?",   a: "Ensure your uploaded image is clear and high resolution. Blurry or low-quality scans may affect detection accuracy." },
    { q: "Do I need an internet connection to use TRACE?", a: "Yes, TRACE requires an internet connection to perform AI-powered analysis on the server." },
    { q: "How do I contact a support representative?",     a: "Email support@trace.app — we respond within 24 hours on business days." },
    { q: "Error: No results detected — what does this mean?", a: "This usually means the uploaded image quality is too low, or the plan type selection does not match the file." },
  ];

  const steps = [
    "Create an account and log in to access your dashboard",
    "Start a new project and select the appropriate plan type",
    "Upload your plan image (PNG, JPG, or PDF)",
    "Wait for TRACE to scan and analyze your plan",
    "Review the generated material table and export your report",
  ];

  return (
    <div className="p-10 max-w-2xl animate-page-in">
      <SectionBar>Help Center</SectionBar>

      <div className="border border-border rounded-lg bg-card overflow-hidden mb-6">
        <div className="px-6 py-5 border-b border-border">
          <p className="text-[13px] font-mono font-semibold text-foreground mb-2">Getting Started with TRACE</p>
          <p className="text-[11px] font-mono text-muted-foreground leading-relaxed">
            TRACE is a material cost estimation platform powered by AI. Upload your architectural plans
            — Floor, Electrical, or Plumbing — and TRACE will automatically detect and quantify all
            relevant materials, providing you with accurate cost breakdowns in seconds.
          </p>
        </div>
        <div className="px-6 py-5 space-y-2">
          {steps.map((step, i) => (
            <div key={i} className="flex items-start gap-3">
              <span className="text-[10px] font-mono text-muted-foreground/50 w-4 shrink-0 mt-0.5">{i + 1}.</span>
              <span className="text-[11px] font-mono text-muted-foreground">{step}</span>
            </div>
          ))}
        </div>
      </div>

      <Mono className="text-[11px] block mb-4">Frequently Asked Questions</Mono>
      <div className="border border-border rounded-lg overflow-hidden divide-y divide-border">
        {faqs.map((faq, i) => (
          <div key={i}>
            <button
              onClick={() => setOpen(open === i ? null : i)}
              className="w-full flex items-center justify-between px-5 py-4 text-left hover:bg-accent/30 transition-colors"
            >
              <span className="text-[11px] font-mono text-foreground pr-4">{faq.q}</span>
              <ChevronDown size={12} className={`text-muted-foreground shrink-0 transition-transform ${open === i ? "rotate-180" : ""}`} />
            </button>
            {open === i && (
              <div className="px-5 pb-4 border-t border-border/50">
                <p className="text-[11px] font-mono text-muted-foreground leading-relaxed pt-3">{faq.a}</p>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
