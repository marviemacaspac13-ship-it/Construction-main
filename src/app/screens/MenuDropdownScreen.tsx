import { User, MessageSquare, HelpCircle, ChevronRight, LogOut } from "lucide-react";
import { SectionBar, Mono } from "../components/ui";
import { useNavigate } from "react-router";

export function MenuDropdownScreen() {
  const navigate = useNavigate();
  return (
    <div className="p-10 max-w-lg animate-page-in">
      <SectionBar>Menu Dropdown</SectionBar>

      <div className="flex flex-col items-end gap-4">
        {/* Simulated topbar context */}
        <div className="w-full flex items-center justify-between h-[70px] px-8 border border-border rounded-lg bg-card mb-2">
          <div className="flex items-center gap-4">
            <span className="font-mono font-light text-foreground" style={{ letterSpacing: "12px", fontSize: "15px" }}>TRACE</span>
            <div className="w-px h-4 bg-border" />
            <Mono>User</Mono>
          </div>
          <div className="flex items-center gap-2">
            <button className="flex items-center gap-2 h-8 px-3 rounded-lg border border-border text-muted-foreground text-[10px] font-mono">
              <MessageSquare size={12} />Feedback
            </button>
            <button className="w-8 h-8 flex items-center justify-center rounded-lg border border-border text-muted-foreground">
              <HelpCircle size={14} />
            </button>
            <button className="w-8 h-8 rounded-full border border-border bg-accent flex items-center justify-center">
              <User size={13} className="text-muted-foreground" />
            </button>
          </div>
        </div>

        {/* Dropdown card */}
        <div className="w-56 bg-popover border border-border rounded-lg overflow-hidden shadow-xl">
          <div className="flex items-center gap-3 px-4 py-4 border-b border-border">
            <div className="w-9 h-9 rounded-full bg-accent border border-border flex items-center justify-center shrink-0">
              <User size={14} className="text-muted-foreground" />
            </div>
            <div className="min-w-0">
              <p className="text-[12px] font-mono text-foreground font-medium">User</p>
              <p className="text-[10px] font-mono text-muted-foreground truncate">user@email.com</p>
            </div>
          </div>
          <button
            onClick={() => navigate("/profile")}
            className="w-full flex items-center gap-3 px-4 py-3 text-[11px] font-mono text-foreground hover:bg-accent border-b border-border transition-colors"
          >
            <User size={12} className="text-muted-foreground" />
            Profile
            <ChevronRight size={10} className="text-muted-foreground ml-auto" />
          </button>
          <button
            onClick={() => navigate("/sign-in")}
            className="w-full flex items-center gap-3 px-4 py-3 text-[11px] font-mono text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
          >
            <LogOut size={12} className="text-muted-foreground" />
            Logout
          </button>
        </div>

        <p className="text-[10px] font-mono text-muted-foreground/40">Profile dropdown — opens from the avatar button in the top bar</p>
      </div>
    </div>
  );
}
