import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Building2,
  Check,
  Copy,
  Database,
  Eye,
  EyeOff,
  KeyRound,
  Palette,
  Server,
} from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Topbar } from "@/components/Topbar";
import { getPaths } from "@/lib/api";

export function Settings() {
  const paths = useQuery({ queryKey: ["paths"], queryFn: getPaths });

  return (
    <div className="flex flex-col">
      <Topbar
        title="Settings"
        subtitle="How AI-DMS files your documents"
      />

      <div className="mx-auto w-full max-w-5xl px-6 py-6">
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          {/* Workspace + token */}
          <div className="space-y-4 lg:col-span-1">
            <WorkspaceCard />
            <TokenCard />
          </div>

          {/* Filing scheme + storage + theme */}
          <div className="space-y-4 lg:col-span-2">
            <Card>
              <CardHeader
                title="Filing scheme"
                subtitle="Deterministic — derived from each document's parsed metadata"
                trailing={<Badge tone="accent" size="sm">Fixed</Badge>}
              />
              <CardBody className="pt-3 space-y-3">
                <div className="rounded-md border border-border bg-canvas px-3 py-2.5 font-mono text-[12.5px] text-accent-ink">
                  AI-DMS / &lt;DocumentType&gt; / &lt;Entity-or-Person&gt; / &lt;original_name&gt;
                </div>
                <ul className="space-y-1.5 text-[12px] text-ink-2">
                  <li>
                    <b className="text-ink-1">DocumentType</b> — one of the 100 UAE-BFSI
                    categories the vision model is constrained to.
                  </li>
                  <li>
                    <b className="text-ink-1">Entity-or-Person</b> — issuing /
                    owning organisation if present; else the natural person; else{" "}
                    <code className="rounded bg-canvas px-1 py-0.5 font-mono text-[11px] text-accent-ink">
                      Unattributed
                    </code>
                    . Matched case-insensitively against existing folders so the
                    same entity never spawns duplicates.
                  </li>
                </ul>
              </CardBody>
            </Card>

            <Card>
              <CardHeader
                title="Storage & inference"
                subtitle="Where your data lives and how it's parsed"
              />
              <CardBody className="pt-3 space-y-2">
                <PathRow
                  icon={Database}
                  label="Staging bucket"
                  value={paths.data?.app_data}
                  hint="Where uploads land before parsing — wiped after each job"
                />
                <PathRow
                  icon={Database}
                  label="Organised bucket"
                  value={paths.data?.organized_root}
                  hint="Where AI-DMS files every classified document"
                />
                <PathRow
                  icon={Server}
                  label="LLM"
                  value={paths.data?.engine_dir}
                  hint="Vision + text classification, plus speech-to-text"
                />
              </CardBody>
            </Card>

            <Card>
              <CardHeader
                title="Appearance"
                subtitle="Light theme, fixed"
                trailing={<Palette className="h-3.5 w-3.5 text-ink-3" />}
              />
              <CardBody className="pt-3 text-[12px] text-ink-3">
                AllysAI DMS uses a single light theme so every surface stays high
                contrast for long reading sessions.
              </CardBody>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}

function WorkspaceCard() {
  return (
    <Card>
      <CardHeader title="Workspace" />
      <CardBody className="pt-2 space-y-3">
        <div className="flex items-start gap-2.5">
          <Building2 className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
          <div className="min-w-0">
            <div className="text-[13px] font-semibold text-ink-1">AI-DMS</div>
            <div className="mt-0.5 text-[11px] text-ink-3">Single tenant · web</div>
          </div>
        </div>
      </CardBody>
    </Card>
  );
}

function TokenCard() {
  const [reveal, setReveal] = useState(false);
  const token = readTokenFromHandshake() ?? "(set via VITE_DMS_TOKEN or handshake)";

  function copy() {
    if (token.startsWith("(")) return;
    void navigator.clipboard.writeText(token);
    toast.success("Bearer token copied");
  }

  return (
    <Card>
      <CardHeader title="Bearer token" subtitle="Authentication for the sidecar API" />
      <CardBody className="pt-2 space-y-2">
        <div className="flex items-center gap-2">
          <KeyRound className="h-3.5 w-3.5 shrink-0 text-ink-3" />
          <div
            className="min-w-0 flex-1 truncate rounded-md border border-border bg-canvas px-2 py-1 font-mono text-[11px] text-ink-1"
            title={token}
          >
            {reveal ? token : token.replace(/./g, "•")}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            leftIcon={reveal ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
            onClick={() => setReveal((v) => !v)}
          >
            {reveal ? "Hide" : "Reveal"}
          </Button>
          <Button
            variant="primary"
            size="sm"
            leftIcon={<Copy className="h-3 w-3" />}
            onClick={copy}
            disabled={token.startsWith("(")}
          >
            Copy
          </Button>
        </div>
        <p className="text-[10px] text-ink-3">
          Anyone with this token can upload, browse, and delete documents.
          Treat it like a password.
        </p>
      </CardBody>
    </Card>
  );
}

function PathRow({
  icon: Icon,
  label,
  value,
  hint,
}: {
  icon: typeof Database;
  label: string;
  value?: string;
  hint?: string;
}) {
  return (
    <div className="flex items-start gap-2.5 rounded-md px-2.5 py-2 hover:bg-sunken">
      <Icon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-ink-3" />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="text-[12px] text-ink-2">{label}</span>
          <Check className="h-3 w-3 text-accent" />
        </div>
        <div className="mt-0.5 truncate font-mono text-[11px] text-ink-1" title={value}>
          {value ?? "…"}
        </div>
        {hint && <div className="mt-0.5 text-[10px] text-ink-3">{hint}</div>}
      </div>
    </div>
  );
}

function readTokenFromHandshake(): string | null {
  if (typeof window === "undefined") return null;
  // Mirrors what api.ts reads on first call.
  const dev = (window as unknown as { __DMS_DEV__?: { token?: string } }).__DMS_DEV__;
  return dev?.token ?? null;
}
