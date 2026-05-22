import {
  BookOpen,
  Boxes,
  Braces,
  FileSearch,
  GitBranch,
  Home,
  Network,
  Server,
  Terminal,
} from "lucide-react";
import type { ReactNode } from "react";

const BG = "#253325";
const INK = "#efe8d5";
const MUTED = "rgba(239,232,213,0.62)";
const FAINT = "rgba(239,232,213,0.10)";
const LINE = "rgba(239,232,213,0.24)";
const GOLD = "#d7b46a";
const ROOT = "#91b88e";

const sections = [
  { id: "overview", label: "Overview" },
  { id: "concepts", label: "Core concepts" },
  { id: "architecture", label: "How it works" },
  { id: "local", label: "Local setup" },
  { id: "mcp", label: "MCP server" },
  { id: "canopy", label: "DataCanopy" },
  { id: "reference", label: "Reference" },
];

const commands = [
  "pip install -e .",
  "dataroot profile ExampleData/AustinPermits/raw",
  "dataroot link",
  "dataroot ask \"Which permit review is delayed and why?\"",
];

function CodeBlock({ children }: { children: string }) {
  return (
    <pre style={{
      margin: "14px 0 0",
      padding: "16px",
      border: `1px solid ${LINE}`,
      borderRadius: 8,
      background: "rgba(0,0,0,0.22)",
      color: INK,
      overflowX: "auto",
      fontSize: 13,
      lineHeight: 1.65,
    }}>
      <code>{children}</code>
    </pre>
  );
}

function Callout({
  title,
  children,
  tone = "default",
}: {
  title: string;
  children: string;
  tone?: "default" | "local" | "tba";
}) {
  const color = tone === "tba" ? GOLD : tone === "local" ? ROOT : INK;
  return (
    <div style={{
      border: `1px dashed ${LINE}`,
      borderLeft: `4px solid ${color}`,
      borderRadius: 8,
      background: FAINT,
      padding: "14px 16px",
      marginTop: 16,
    }}>
      <strong style={{ display: "block", color, fontSize: 13, marginBottom: 5 }}>{title}</strong>
      <p style={{ margin: 0, color: MUTED, fontSize: 14, lineHeight: 1.65 }}>{children}</p>
    </div>
  );
}

function Section({
  id,
  icon,
  title,
  children,
}: {
  id: string;
  icon: ReactNode;
  title: string;
  children: ReactNode;
}) {
  return (
    <section id={id} style={{
      scrollMarginTop: 24,
      borderTop: `1px dashed ${LINE}`,
      padding: "42px 0",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
        <span style={{
          width: 34,
          height: 34,
          borderRadius: 8,
          display: "grid",
          placeItems: "center",
          background: FAINT,
          color: ROOT,
          border: `1px solid ${LINE}`,
        }}>
          {icon}
        </span>
        <h2 style={{ margin: 0, color: INK, fontSize: "clamp(26px,4vw,38px)", lineHeight: 1.05 }}>
          {title}
        </h2>
      </div>
      <div className="docs-prose">{children}</div>
    </section>
  );
}

function DocsRootDiagram() {
  const nodes = [
    ["Sources", "CSV, JSON, Markdown, repos", 8, 28],
    ["Profile", "Tables, fields, records", 31, 64],
    ["Link", "IDs, addresses, references", 53, 30],
    ["Retrieve", "Bounded tool calls", 69, 70],
    ["Answer", "Citations + source trail", 82, 34],
  ] as const;

  return (
    <div style={{
      position: "relative",
      minHeight: 270,
      border: `1px dashed ${LINE}`,
      borderRadius: 10,
      background:
        "linear-gradient(90deg, rgba(239,232,213,0.04) 1px, transparent 1px), linear-gradient(0deg, rgba(239,232,213,0.04) 1px, transparent 1px), rgba(0,0,0,0.10)",
      backgroundSize: "34px 34px",
      overflow: "hidden",
      marginTop: 24,
    }}>
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
        <path d="M16 44 C 30 35, 34 70, 43 76 S 55 43, 62 44 S 72 82, 79 76 S 84 44, 90 50" fill="none" stroke={ROOT} strokeOpacity="0.55" strokeWidth="0.55" vectorEffect="non-scaling-stroke" />
        <path d="M18 50 C 32 61, 41 39, 51 43 S 64 65, 72 61 S 81 37, 90 43" fill="none" stroke={GOLD} strokeOpacity="0.45" strokeWidth="0.45" vectorEffect="non-scaling-stroke" />
      </svg>
      {nodes.map(([title, body, left, top]) => (
        <div key={title} style={{
          position: "absolute",
          left: `${left}%`,
          top: `${top}%`,
          transform: "translate(-50%, -50%)",
          width: 150,
          minHeight: 74,
          border: `1px solid ${LINE}`,
          borderRadius: 8,
          background: "rgba(29,43,29,0.94)",
          padding: "12px 14px",
          boxShadow: "0 14px 36px rgba(0,0,0,0.20)",
        }}>
          <strong style={{ display: "block", color: INK, fontSize: 14, marginBottom: 5 }}>{title}</strong>
          <span style={{ color: MUTED, fontSize: 12, lineHeight: 1.4 }}>{body}</span>
        </div>
      ))}
    </div>
  );
}

export function DocsPage() {
  return (
    <main style={{
      minHeight: "100vh",
      background:
        "radial-gradient(circle at 14% 4%, rgba(145,184,142,0.14), transparent 28%), radial-gradient(circle at 86% 16%, rgba(215,180,106,0.10), transparent 26%), #253325",
      color: INK,
      fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif",
    }}>
      <style>{`
        .docs-prose p { margin: 0 0 14px; color: ${MUTED}; line-height: 1.75; font-size: 15px; }
        .docs-prose ul { margin: 14px 0 0; padding-left: 20px; color: ${MUTED}; line-height: 1.7; }
        .docs-prose li { margin: 7px 0; }
        .docs-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; margin-top: 18px; }
        .docs-card { border: 1px dashed ${LINE}; border-radius: 8px; padding: 16px; background: ${FAINT}; }
        .docs-card strong { display: block; color: ${INK}; margin-bottom: 7px; }
        @media (max-width: 880px) {
          .docs-layout { grid-template-columns: 1fr !important; }
          .docs-sidebar { position: static !important; }
          .docs-grid { grid-template-columns: 1fr; }
        }
      `}</style>

      <header style={{
        borderBottom: `1px dashed ${LINE}`,
        background: "rgba(29,43,29,0.62)",
        backdropFilter: "blur(14px)",
      }}>
        <div style={{
          maxWidth: 1180,
          margin: "0 auto",
          padding: "18px 24px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 18,
        }}>
          <a href="/" style={{ display: "flex", alignItems: "center", gap: 10, color: INK, textDecoration: "none", fontWeight: 800 }}>
            <span style={{
              width: 34,
              height: 34,
              display: "grid",
              placeItems: "center",
              borderRadius: 8,
              background: ROOT,
              color: BG,
            }}>
              <Network size={18} />
            </span>
            DataRoot Docs
          </a>
          <nav style={{ display: "flex", alignItems: "center", gap: 14, color: MUTED, fontSize: 14 }}>
            <a href="/" style={{ color: MUTED, textDecoration: "none", display: "flex", alignItems: "center", gap: 6 }}>
              <Home size={15} /> Home
            </a>
            <a href="/#waitlist" style={{ color: MUTED, textDecoration: "none" }}>Waitlist</a>
          </nav>
        </div>
      </header>

      <div className="docs-layout" style={{
        maxWidth: 1180,
        margin: "0 auto",
        padding: "54px 24px 80px",
        display: "grid",
        gridTemplateColumns: "230px minmax(0, 1fr)",
        gap: 42,
      }}>
        <aside className="docs-sidebar" style={{ position: "sticky", top: 24, alignSelf: "start" }}>
          <div style={{
            border: `1px dashed ${LINE}`,
            borderRadius: 10,
            background: "rgba(29,43,29,0.74)",
            padding: 14,
          }}>
            <p style={{
              margin: "0 0 10px",
              color: GOLD,
              fontSize: 11,
              fontWeight: 800,
              letterSpacing: "0.14em",
              textTransform: "uppercase",
              fontFamily: "monospace",
            }}>
              Documentation
            </p>
            {sections.map((section) => (
              <a key={section.id} href={`#${section.id}`} style={{
                display: "block",
                padding: "8px 9px",
                borderRadius: 6,
                color: MUTED,
                textDecoration: "none",
                fontSize: 14,
              }}>
                {section.label}
              </a>
            ))}
          </div>
        </aside>

        <article>
          <p style={{
            margin: "0 0 18px",
            color: GOLD,
            fontSize: 12,
            fontWeight: 800,
            letterSpacing: "0.16em",
            textTransform: "uppercase",
            fontFamily: "monospace",
          }}>
            context infrastructure
          </p>
          <h1 style={{
            margin: 0,
            maxWidth: 820,
            color: INK,
            fontSize: "clamp(48px,8vw,86px)",
            lineHeight: 0.96,
            letterSpacing: 0,
          }}>
            Build answers from rooted context.
          </h1>
          <p style={{
            maxWidth: 760,
            margin: "24px 0 0",
            color: MUTED,
            fontSize: 19,
            lineHeight: 1.65,
          }}>
            DataRoot turns scattered project or organization files into a linked knowledge layer that agents and teams can query. The system is designed around provenance: answers should carry the source trail that produced them.
          </p>

          <DocsRootDiagram />

          <Section id="overview" icon={<BookOpen size={18} />} title="Overview">
            <p>
              DataRoot is the foundation layer for private organizational context. It profiles source files, links related records, and exposes a retrieval surface that can be used by humans, application UI, and agent clients.
            </p>
            <p>
              The goal is not to replace your documents or databases. The goal is to make the useful context inside them easier to traverse, cite, and reuse.
            </p>
            <Callout title="Current status" tone="tba">
              This documentation is a working reference for the current system. Some hosted, team, and production deployment details are still TBA.
            </Callout>
          </Section>

          <Section id="concepts" icon={<Boxes size={18} />} title="Core Concepts">
            <div className="docs-grid">
              <div className="docs-card">
                <strong>Workspace</strong>
                <p>A bounded collection of files and generated records, such as a project, department dataset, or customer context pack.</p>
              </div>
              <div className="docs-card">
                <strong>Source trail</strong>
                <p>The ordered evidence path behind an answer: files, records, rows, notes, and relationships used to form the response.</p>
              </div>
              <div className="docs-card">
                <strong>Knowledge graph</strong>
                <p>A linked representation of source records and relationships discovered from IDs, table structure, addresses, and references.</p>
              </div>
              <div className="docs-card">
                <strong>DataCanopy</strong>
                <p>The visual layer for inspecting the system: ERD, DFD, schema, source relationships, and answer paths.</p>
              </div>
            </div>
          </Section>

          <Section id="architecture" icon={<GitBranch size={18} />} title="How It Works">
            <p>
              DataRoot follows a repeatable flow: ingest files, profile their structure, link related records, retrieve relevant context, and answer with citations.
            </p>
            <ul>
              <li><strong>Ingest:</strong> read CSV, JSON, Markdown, FASTA, spreadsheet exports, and project documents.</li>
              <li><strong>Profile:</strong> detect tables, columns, row groups, record types, and domain hints.</li>
              <li><strong>Link:</strong> connect repeated IDs, references, normalized fields, and address-like joins.</li>
              <li><strong>Retrieve:</strong> use bounded tools to search, traverse, list, and inspect records.</li>
              <li><strong>Answer:</strong> compose a response with source-backed evidence instead of unsupported guesses.</li>
            </ul>
          </Section>

          <Section id="local" icon={<Terminal size={18} />} title="Local Setup">
            <p>
              Local DataRoot is the full-power mode. It can access private files on your machine, build local workspaces, run agent-facing services, and connect to tools that are not available from a hosted browser page.
            </p>
            <CodeBlock>{commands.join("\n")}</CodeBlock>
            <Callout title="Local-only capability" tone="local">
              Filesystem access, private workspaces, and agent client integration should run locally or in a trusted private environment. Hosted pages can explain or preview the workflow, but they should not silently reach into private folders.
            </Callout>
          </Section>

          <Section id="mcp" icon={<Server size={18} />} title="MCP Server">
            <p>
              The MCP server is the method for giving external agents a controlled way to use DataRoot. Instead of handing an agent an entire folder, DataRoot exposes a small set of bounded tools.
            </p>
            <ul>
              <li><strong>Discovery:</strong> list available workspaces and summarize what each contains.</li>
              <li><strong>Search:</strong> find relevant records with result limits.</li>
              <li><strong>Traversal:</strong> inspect graph neighborhoods without unbounded expansion.</li>
              <li><strong>Evidence:</strong> fetch specific records and cite the source material used.</li>
              <li><strong>Answering:</strong> let the agent build responses from retrieved context.</li>
            </ul>
            <CodeBlock>{[
              "dataroot mcp",
              "# or",
              "python -m dataroot.mcp",
              "# Windows/WSL launcher",
              "bash scripts/start-mcp.sh",
            ].join("\n")}</CodeBlock>
            <Callout title="Why MCP matters" tone="local">
              MCP keeps the agent interface explicit. The agent asks DataRoot for bounded context instead of guessing which file to open or loading an entire project into chat.
            </Callout>
          </Section>

          <Section id="canopy" icon={<FileSearch size={18} />} title="DataCanopy">
            <p>
              DataCanopy is the visual inspection layer. It makes the knowledge base legible by showing the shape of the data, where context enters the system, and how answers move through source records.
            </p>
            <p>
              ERD views are useful for understanding entities and relationships. DFD views are useful for explaining movement: what question enters, which stores are queried, and how cited answers are assembled.
            </p>
            <Callout title="Work in progress" tone="tba">
              Highlighting exact source nodes from an answer path inside the canvas is planned. The current system already separates the answer trail and the editable visual model.
            </Callout>
          </Section>

          <Section id="reference" icon={<Braces size={18} />} title="Reference">
            <div className="docs-grid">
              <div className="docs-card">
                <strong>Primary commands</strong>
                <p><code>dataroot profile</code>, <code>dataroot link</code>, <code>dataroot ask</code>, and <code>dataroot mcp</code>.</p>
              </div>
              <div className="docs-card">
                <strong>Common workspaces</strong>
                <p>Austin permits, agriculture traits, fermentation research, and project-specific folders.</p>
              </div>
              <div className="docs-card">
                <strong>Safety model</strong>
                <p>Prefer bounded retrieval, explicit source trails, scoped tools, and local execution for private files.</p>
              </div>
              <div className="docs-card">
                <strong>Production notes</strong>
                <p>Team auth, managed deployment, and sync workflows are TBA while the local methodology stabilizes.</p>
              </div>
            </div>
            <Callout title="Design principle" tone="local">
              DataRoot should make context reusable without making it uncontrolled. Local setup is the trusted path for private data; hosted surfaces should stay explicit about what they can and cannot access.
            </Callout>
          </Section>
        </article>
      </div>
    </main>
  );
}
