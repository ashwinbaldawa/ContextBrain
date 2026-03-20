import { useState, useRef, useEffect, useCallback } from "react";

// --- Mock data ---
const INITIAL_CATALOG = [
  {
    id: "1", name: "Member Eligibility API", version: "3.2.0", domain: "benefits",
    owner_team: "Benefits Platform Team", owner_contact: "jane.doe@example.com",
    status: "active", auth_mechanism: "HTTP Bearer",
    business_description: "Verifies member coverage and benefit eligibility for medical, behavioral health, and pharmacy.",
    base_url: "https://api.internal.example.com/eligibility/v3",
    created_at: "2025-01-15", updated_at: "2025-03-01",
    endpoints: [
      { method: "GET", path: "/members/{memberId}/eligibility", summary: "Check member eligibility status" },
      { method: "GET", path: "/members/{memberId}/benefits/{serviceCategory}", summary: "Check benefit coverage for a specific service" },
      { method: "POST", path: "/members/batch-eligibility", summary: "Batch eligibility check for up to 100 members" },
    ],
    annotations: [
      { content: "Dental and vision have separate endpoints — this API only covers medical and behavioral health.", author: "dev_smith", category: "gotcha" },
      { content: "Returns empty response for dependent-only plans. Must pass the subscriber's member ID.", author: "dev_patel", category: "gotcha" },
    ],
  },
  {
    id: "2", name: "Claims Processing API", version: "2.1.0", domain: "claims",
    owner_team: "Claims Engine Team", owner_contact: "bob.smith@example.com",
    status: "active", auth_mechanism: "OAuth2",
    business_description: "Query and manage health insurance claims including submission, status lookup, and EOB retrieval.",
    created_at: "2025-01-10", updated_at: "2025-03-08", endpoints: [], annotations: [],
  },
  {
    id: "3", name: "Provider Network API", version: "4.0.1", domain: "provider",
    owner_team: "Provider Data Team", owner_contact: "carol.jones@example.com",
    status: "active", auth_mechanism: "API Key (header)",
    business_description: "Search providers by specialty, location, and network. Check availability and in-network status.",
    created_at: "2025-01-12", updated_at: "2025-02-28", endpoints: [], annotations: [],
  },
  {
    id: "4", name: "Prior Authorization API", version: "2.3.0", domain: "utilization_management",
    owner_team: "UM Platform Team", owner_contact: "dave.wilson@example.com",
    status: "active", auth_mechanism: "HTTP Bearer",
    business_description: "Manage prior authorization requests — submission, status checks, and clinical review workflows.",
    created_at: "2025-01-20", updated_at: "2025-03-05", endpoints: [], annotations: [],
  },
];

const MOCK_CHAT_RESPONSE = `I found **2 APIs** relevant to checking member eligibility for behavioral health services:

**1. Member Eligibility API (v3.2.0)** — Benefits Platform Team
Use the endpoint:
• \`GET /members/{memberId}/benefits/behavioral_health\`

⚠️ **Gotcha**: This API only covers medical and behavioral health. Dental/vision have separate endpoints.
⚠️ **Gotcha**: Returns empty for dependent-only plans — use the subscriber's member ID.

**2. Prior Authorization API (v2.3.0)** — UM Platform Team
After confirming coverage, check if the procedure needs prior auth:
• \`GET /services/{procedureCode}/auth-required?planId=...\`

⚠️ **Critical**: Always call eligibility first. The prior auth API assumes active coverage.

**Recommended flow**: Eligibility → confirm coverage → check prior auth requirement → submit if needed.`;

// --- Spec Parser (client-side, mirrors backend logic) ---
function parseSpec(spec) {
  const info = spec.info || {};
  const isV3 = (spec.openapi || "").startsWith("3");
  let baseUrl = "";
  if (isV3 && spec.servers?.[0]) baseUrl = spec.servers[0].url || "";
  else if (spec.host) baseUrl = `${(spec.schemes || ["https"])[0]}://${spec.host}${spec.basePath || ""}`;

  let auth = null;
  const schemes = isV3 ? spec.components?.securitySchemes : spec.securityDefinitions;
  if (schemes) {
    for (const [, s] of Object.entries(schemes)) {
      if (s.type === "oauth2") { auth = "OAuth2"; break; }
      if (s.type === "apiKey") { auth = `API Key (${s.in || "header"})`; break; }
      if (s.type === "http") { auth = `HTTP ${(s.scheme || "bearer").charAt(0).toUpperCase() + (s.scheme || "bearer").slice(1)}`; break; }
    }
  }

  const endpoints = [];
  for (const [path, item] of Object.entries(spec.paths || {})) {
    for (const method of ["get", "post", "put", "patch", "delete"]) {
      if (!item[method]) continue;
      const op = item[method];
      endpoints.push({
        method: method.toUpperCase(),
        path,
        summary: op.summary || op.description || `${method.toUpperCase()} ${path}`,
      });
    }
  }

  return {
    name: info.title || "Untitled API",
    version: info.version || "1.0.0",
    description: info.description || "",
    base_url: baseUrl,
    auth_mechanism: auth,
    endpoints,
  };
}

// --- Shared Components ---
function CategoryBadge({ category }) {
  const colors = { gotcha: { bg: "#FEF2F2", text: "#991B1B", border: "#FECACA" }, workaround: { bg: "#FFF7ED", text: "#9A3412", border: "#FED7AA" }, tip: { bg: "#F0FDF4", text: "#166534", border: "#BBF7D0" }, correction: { bg: "#EFF6FF", text: "#1E40AF", border: "#BFDBFE" }, deprecation: { bg: "#FAF5FF", text: "#6B21A8", border: "#E9D5FF" } };
  const c = colors[category] || colors.tip;
  return <span style={{ fontSize: 10, fontWeight: 600, padding: "2px 8px", borderRadius: 99, background: c.bg, color: c.text, border: `1px solid ${c.border}`, textTransform: "uppercase", letterSpacing: "0.05em" }}>{category}</span>;
}

function AnnotationCard({ annotation }) {
  return (
    <div style={{ display: "flex", gap: 8, alignItems: "flex-start", padding: "8px 12px", background: "var(--bg-annotation)", borderRadius: 8, border: "1px solid var(--border-subtle)", fontSize: 13 }}>
      <span style={{ fontSize: 14, flexShrink: 0 }}>⚠️</span>
      <div style={{ flex: 1 }}>
        <div style={{ display: "flex", gap: 6, alignItems: "center", marginBottom: 4 }}>
          <CategoryBadge category={annotation.category} />
          <span style={{ color: "var(--text-muted)", fontSize: 11 }}>@{annotation.author}</span>
        </div>
        <p style={{ margin: 0, color: "var(--text-primary)", lineHeight: 1.45 }}>{annotation.content}</p>
      </div>
    </div>
  );
}

function EndpointRow({ endpoint }) {
  const mc = { GET: "#16A34A", POST: "#2563EB", PUT: "#D97706", PATCH: "#8B5CF6", DELETE: "#DC2626" };
  return (
    <div style={{ display: "flex", gap: 8, alignItems: "center", padding: "6px 0", borderBottom: "1px solid var(--border-subtle)" }}>
      <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 11, fontWeight: 700, color: mc[endpoint.method] || "#6B7280", minWidth: 48 }}>{endpoint.method}</span>
      <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 12, color: "var(--text-primary)", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{endpoint.path}</span>
      <span style={{ fontSize: 12, color: "var(--text-muted)", maxWidth: "40%", textAlign: "right", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{endpoint.summary}</span>
    </div>
  );
}

function ApiCard({ result, onDelete }) {
  const a = result.api || result;
  const endpoints = result.endpoints || a.endpoints || [];
  const annotations = result.annotations || a.annotations || [];
  const score = result.relevance_score;
  return (
    <div style={{ background: "var(--bg-card)", border: "1px solid var(--border-card)", borderRadius: 12, padding: 16, marginBottom: 12 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <h3 style={{ margin: 0, fontSize: 15, fontWeight: 700, color: "var(--text-primary)" }}>
            {a.name} <span style={{ fontWeight: 400, fontSize: 12, color: "var(--text-muted)" }}>v{a.version}</span>
          </h3>
          <div style={{ display: "flex", gap: 6, marginTop: 4, flexWrap: "wrap" }}>
            {a.domain && <span style={{ fontSize: 11, padding: "2px 8px", borderRadius: 99, background: "var(--bg-tag)", color: "var(--text-tag)", fontWeight: 500 }}>{a.domain}</span>}
            <span style={{ fontSize: 11, padding: "2px 8px", borderRadius: 99, background: a.status === "active" ? "#0D3320" : "#3D2F04", color: a.status === "active" ? "#4ADE80" : "#FACC15", fontWeight: 500, border: `1px solid ${a.status === "active" ? "#166534" : "#854D0E"}` }}>{a.status}</span>
            {a.auth_mechanism && <span style={{ fontSize: 11, padding: "2px 8px", borderRadius: 99, background: "var(--bg-tag)", color: "var(--text-tag)" }}>🔒 {a.auth_mechanism}</span>}
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "flex-start", flexShrink: 0 }}>
          {score != null && (
            <div style={{ fontSize: 11, color: "var(--text-muted)", textAlign: "right" }}>
              <div style={{ fontSize: 20, fontWeight: 800, color: score > 0.8 ? "#4ADE80" : score > 0.5 ? "#FACC15" : "#6B7280", lineHeight: 1 }}>{(score * 100).toFixed(0)}%</div>
              <span>match</span>
            </div>
          )}
          {onDelete && (
            <button onClick={() => onDelete(a.id)} style={{ fontSize: 16, background: "none", border: "none", cursor: "pointer", color: "var(--text-muted)", padding: 4, borderRadius: 4 }} title="Remove from catalog">×</button>
          )}
        </div>
      </div>
      {(a.business_description || a.description) && <p style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.55, margin: "8px 0" }}>{a.business_description || a.description}</p>}
      {a.owner_team && <p style={{ fontSize: 12, color: "var(--text-muted)", margin: "4px 0" }}>👥 {a.owner_team} {a.owner_contact ? `· ${a.owner_contact}` : ""}</p>}
      {a.base_url && <p style={{ fontSize: 11, color: "var(--text-muted)", fontFamily: "'IBM Plex Mono', monospace", margin: "4px 0" }}>🌐 {a.base_url}</p>}
      {endpoints.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <p style={{ fontSize: 11, fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>Endpoints ({endpoints.length})</p>
          <div style={{ maxHeight: 180, overflowY: "auto" }}>{endpoints.map((ep, i) => <EndpointRow key={i} endpoint={ep} />)}</div>
        </div>
      )}
      {annotations.length > 0 && (
        <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 6 }}>
          <p style={{ fontSize: 11, fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 0 }}>Developer Notes ({annotations.length})</p>
          {annotations.map((ann, i) => <AnnotationCard key={i} annotation={ann} />)}
        </div>
      )}
    </div>
  );
}

function ChatMessage({ msg }) {
  return (
    <div style={{ display: "flex", gap: 12, padding: "14px 0" }}>
      <div style={{ width: 32, height: 32, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14, flexShrink: 0, background: msg.role === "user" ? "var(--accent)" : "linear-gradient(135deg, #6366F1, #8B5CF6)", color: "#fff", fontWeight: 700 }}>
        {msg.role === "user" ? "A" : "🧠"}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <p style={{ fontSize: 11, fontWeight: 600, color: "var(--text-muted)", margin: "0 0 6px", textTransform: "uppercase", letterSpacing: "0.05em" }}>{msg.role === "user" ? "You" : "ContextBrain"}</p>
        <div style={{ fontSize: 13.5, lineHeight: 1.65, color: "var(--text-primary)", whiteSpace: "pre-wrap" }}>{msg.content}</div>
        {msg.apis?.length > 0 && (
          <div style={{ marginTop: 14 }}>{msg.apis.map((r, i) => <ApiCard key={i} result={r} />)}</div>
        )}
      </div>
    </div>
  );
}

// --- Upload Panel ---
function UploadPanel({ onIngest }) {
  const [dragOver, setDragOver] = useState(false);
  const [parsedSpec, setParsedSpec] = useState(null);
  const [rawJson, setRawJson] = useState("");
  const [parseError, setParseError] = useState(null);
  const [meta, setMeta] = useState({ domain: "", owner_team: "", owner_contact: "", gateway_id: "" });
  const [uploadMode, setUploadMode] = useState("file"); // file | paste
  const [successMsg, setSuccessMsg] = useState(null);
  const fileInputRef = useRef(null);

  const handleFile = useCallback((file) => {
    if (!file) return;
    setParseError(null);
    setParsedSpec(null);
    setSuccessMsg(null);
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const text = e.target.result;
        setRawJson(text);
        const spec = JSON.parse(text);
        if (!spec.openapi && !spec.swagger) {
          setParseError("This doesn't look like an OpenAPI/Swagger spec. Missing 'openapi' or 'swagger' field.");
          return;
        }
        const parsed = parseSpec(spec);
        setParsedSpec(parsed);
      } catch (err) {
        setParseError(`Invalid JSON: ${err.message}`);
      }
    };
    reader.readAsText(file);
  }, []);

  const handlePaste = useCallback((text) => {
    setRawJson(text);
    setParseError(null);
    setParsedSpec(null);
    setSuccessMsg(null);
    if (!text.trim()) return;
    try {
      const spec = JSON.parse(text);
      if (!spec.openapi && !spec.swagger) {
        setParseError("Missing 'openapi' or 'swagger' field.");
        return;
      }
      setParsedSpec(parseSpec(spec));
    } catch (err) {
      setParseError(`Invalid JSON: ${err.message}`);
    }
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file && (file.name.endsWith(".json") || file.name.endsWith(".yaml") || file.name.endsWith(".yml"))) {
      handleFile(file);
    } else {
      setParseError("Please drop a .json or .yaml file");
    }
  }, [handleFile]);

  const handleSubmit = () => {
    if (!parsedSpec) return;
    const newApi = {
      id: `uploaded-${Date.now()}`,
      name: parsedSpec.name,
      version: parsedSpec.version,
      domain: meta.domain || null,
      owner_team: meta.owner_team || null,
      owner_contact: meta.owner_contact || null,
      status: "active",
      auth_mechanism: parsedSpec.auth_mechanism,
      business_description: parsedSpec.description,
      description: parsedSpec.description,
      base_url: parsedSpec.base_url,
      gateway_id: meta.gateway_id || null,
      created_at: new Date().toISOString().split("T")[0],
      updated_at: new Date().toISOString().split("T")[0],
      endpoints: parsedSpec.endpoints,
      annotations: [],
    };
    onIngest(newApi);
    setSuccessMsg(`"${parsedSpec.name}" added to catalog with ${parsedSpec.endpoints.length} endpoints`);
    setParsedSpec(null);
    setRawJson("");
    setMeta({ domain: "", owner_team: "", owner_contact: "", gateway_id: "" });
  };

  const handleReset = () => {
    setParsedSpec(null);
    setRawJson("");
    setParseError(null);
    setSuccessMsg(null);
    setMeta({ domain: "", owner_team: "", owner_contact: "", gateway_id: "" });
  };

  const inputStyle = {
    width: "100%", padding: "10px 12px", borderRadius: 8, border: "1px solid var(--border-card)",
    background: "var(--bg-input)", color: "var(--text-primary)", fontSize: 13, fontFamily: "inherit", outline: "none",
  };
  const labelStyle = { fontSize: 11, fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 4, display: "block" };

  return (
    <div style={{ flex: 1, overflowY: "auto", padding: "24px 28px" }}>
      <div style={{ marginBottom: 20 }}>
        <h2 style={{ margin: 0, fontSize: 22, fontWeight: 800, letterSpacing: "-0.02em" }}>Upload API Spec</h2>
        <p style={{ margin: "4px 0 0", fontSize: 13, color: "var(--text-muted)" }}>Add APIs to the catalog by uploading OpenAPI/Swagger JSON specs</p>
      </div>

      {successMsg && (
        <div style={{ padding: "12px 16px", borderRadius: 10, background: "#0D3320", border: "1px solid #166534", color: "#4ADE80", fontSize: 13, marginBottom: 16, display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 18 }}>✅</span>
          <span style={{ flex: 1 }}>{successMsg}</span>
          <button onClick={() => setSuccessMsg(null)} style={{ background: "none", border: "none", color: "#4ADE80", cursor: "pointer", fontSize: 16 }}>×</button>
        </div>
      )}

      {/* Mode Toggle */}
      <div style={{ display: "flex", gap: 4, marginBottom: 16, background: "var(--bg-tag)", borderRadius: 8, padding: 3, width: "fit-content" }}>
        {[{ id: "file", label: "📁 Upload File" }, { id: "paste", label: "📋 Paste JSON" }].map(m => (
          <button key={m.id} onClick={() => { setUploadMode(m.id); handleReset(); }}
            style={{ padding: "8px 16px", borderRadius: 6, border: "none", fontSize: 12, fontWeight: 600, cursor: "pointer", fontFamily: "inherit", transition: "all 0.15s",
              background: uploadMode === m.id ? "var(--accent)" : "transparent",
              color: uploadMode === m.id ? "#fff" : "var(--text-secondary)",
            }}>
            {m.label}
          </button>
        ))}
      </div>

      {/* File Upload / Paste Area */}
      {!parsedSpec && (
        <>
          {uploadMode === "file" ? (
            <div
              onDragOver={e => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              style={{
                border: `2px dashed ${dragOver ? "var(--accent)" : "var(--border-card)"}`,
                borderRadius: 12, padding: "48px 24px", textAlign: "center", cursor: "pointer",
                background: dragOver ? "rgba(99, 102, 241, 0.08)" : "var(--bg-card)",
                transition: "all 0.2s",
              }}
            >
              <input ref={fileInputRef} type="file" accept=".json,.yaml,.yml" style={{ display: "none" }}
                onChange={e => handleFile(e.target.files[0])} />
              <div style={{ fontSize: 40, marginBottom: 12 }}>📄</div>
              <p style={{ fontSize: 15, fontWeight: 600, color: "var(--text-primary)", margin: "0 0 6px" }}>
                Drop your OpenAPI spec here
              </p>
              <p style={{ fontSize: 13, color: "var(--text-muted)", margin: 0 }}>
                or click to browse · Supports .json and .yaml
              </p>
            </div>
          ) : (
            <div>
              <textarea
                value={rawJson}
                onChange={e => handlePaste(e.target.value)}
                placeholder='Paste your OpenAPI/Swagger JSON here...\n\n{\n  "openapi": "3.0.3",\n  "info": { "title": "My API", ... },\n  "paths": { ... }\n}'
                style={{
                  ...inputStyle,
                  minHeight: 200, resize: "vertical", fontFamily: "'IBM Plex Mono', monospace", fontSize: 12, lineHeight: 1.6,
                }}
              />
            </div>
          )}
        </>
      )}

      {/* Parse Error */}
      {parseError && (
        <div style={{ padding: "12px 16px", borderRadius: 10, background: "#3B1114", border: "1px solid #7F1D1D", color: "#FCA5A5", fontSize: 13, marginTop: 12, display: "flex", gap: 8, alignItems: "flex-start" }}>
          <span>⚠️</span>
          <div>
            <p style={{ margin: 0, fontWeight: 600 }}>Parse Error</p>
            <p style={{ margin: "4px 0 0" }}>{parseError}</p>
          </div>
        </div>
      )}

      {/* Parsed Preview + Metadata Form */}
      {parsedSpec && (
        <div style={{ marginTop: 16 }}>
          {/* Parsed Preview */}
          <div style={{ background: "var(--bg-card)", border: "1px solid var(--border-card)", borderRadius: 12, padding: 16, marginBottom: 16 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <div>
                <p style={{ fontSize: 11, fontWeight: 600, color: "#4ADE80", textTransform: "uppercase", letterSpacing: "0.06em", margin: "0 0 4px" }}>✓ Spec Parsed Successfully</p>
                <h3 style={{ margin: 0, fontSize: 17, fontWeight: 700, color: "var(--text-primary)" }}>
                  {parsedSpec.name} <span style={{ fontWeight: 400, fontSize: 13, color: "var(--text-muted)" }}>v{parsedSpec.version}</span>
                </h3>
              </div>
              <button onClick={handleReset} style={{ fontSize: 12, color: "var(--text-muted)", background: "var(--bg-tag)", border: "none", cursor: "pointer", padding: "6px 12px", borderRadius: 6, fontFamily: "inherit" }}>
                ↩ Start Over
              </button>
            </div>

            {parsedSpec.description && (
              <p style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.55, margin: "8px 0 12px" }}>{parsedSpec.description}</p>
            )}

            <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 12 }}>
              {parsedSpec.base_url && (
                <div style={{ fontSize: 12, color: "var(--text-muted)" }}>
                  <span style={{ fontWeight: 600 }}>Base URL:</span> <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 11 }}>{parsedSpec.base_url}</span>
                </div>
              )}
              {parsedSpec.auth_mechanism && (
                <div style={{ fontSize: 12, color: "var(--text-muted)" }}>
                  <span style={{ fontWeight: 600 }}>Auth:</span> 🔒 {parsedSpec.auth_mechanism}
                </div>
              )}
            </div>

            <p style={{ fontSize: 11, fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>
              Endpoints Detected ({parsedSpec.endpoints.length})
            </p>
            <div style={{ maxHeight: 200, overflowY: "auto" }}>
              {parsedSpec.endpoints.map((ep, i) => <EndpointRow key={i} endpoint={ep} />)}
            </div>
          </div>

          {/* Metadata Form */}
          <div style={{ background: "var(--bg-card)", border: "1px solid var(--border-card)", borderRadius: 12, padding: 16, marginBottom: 16 }}>
            <p style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)", margin: "0 0 16px" }}>
              📝 Add Metadata <span style={{ fontWeight: 400, fontSize: 12, color: "var(--text-muted)" }}>· optional but helps with discovery</span>
            </p>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <div>
                <label style={labelStyle}>Business Domain</label>
                <select value={meta.domain} onChange={e => setMeta(m => ({ ...m, domain: e.target.value }))}
                  style={{ ...inputStyle, cursor: "pointer" }}>
                  <option value="">Select domain...</option>
                  <option value="benefits">Benefits</option>
                  <option value="claims">Claims</option>
                  <option value="provider">Provider</option>
                  <option value="pharmacy">Pharmacy</option>
                  <option value="utilization_management">Utilization Management</option>
                  <option value="care_management">Care Management</option>
                  <option value="member_services">Member Services</option>
                  <option value="analytics">Analytics</option>
                  <option value="other">Other</option>
                </select>
              </div>
              <div>
                <label style={labelStyle}>Gateway ID</label>
                <input value={meta.gateway_id} onChange={e => setMeta(m => ({ ...m, gateway_id: e.target.value }))}
                  placeholder="e.g., AXWAY-BEN-001" style={inputStyle} />
              </div>
              <div>
                <label style={labelStyle}>Owner Team</label>
                <input value={meta.owner_team} onChange={e => setMeta(m => ({ ...m, owner_team: e.target.value }))}
                  placeholder="e.g., Benefits Platform Team" style={inputStyle} />
              </div>
              <div>
                <label style={labelStyle}>Owner Contact</label>
                <input value={meta.owner_contact} onChange={e => setMeta(m => ({ ...m, owner_contact: e.target.value }))}
                  placeholder="e.g., jane.doe@example.com" style={inputStyle} />
              </div>
            </div>
          </div>

          {/* Submit */}
          <div style={{ display: "flex", gap: 12, justifyContent: "flex-end" }}>
            <button onClick={handleReset} style={{ padding: "10px 20px", borderRadius: 8, border: "1px solid var(--border-card)", background: "transparent", color: "var(--text-secondary)", fontSize: 13, cursor: "pointer", fontFamily: "inherit", fontWeight: 600 }}>
              Cancel
            </button>
            <button onClick={handleSubmit} style={{ padding: "10px 24px", borderRadius: 8, border: "none", background: "var(--accent)", color: "#fff", fontSize: 13, cursor: "pointer", fontFamily: "inherit", fontWeight: 700, display: "flex", alignItems: "center", gap: 6 }}>
              <span>📥</span> Add to Catalog
            </button>
          </div>
        </div>
      )}

      {/* Help section */}
      {!parsedSpec && !parseError && (
        <div style={{ marginTop: 24, padding: 16, background: "var(--bg-card)", border: "1px solid var(--border-card)", borderRadius: 12 }}>
          <p style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)", margin: "0 0 8px" }}>💡 What can I upload?</p>
          <p style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.6, margin: 0 }}>
            Any valid OpenAPI 3.x or Swagger 2.x specification in JSON format. The spec should contain at minimum an <code style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 12, background: "var(--bg-tag)", padding: "1px 5px", borderRadius: 4 }}>info</code> block and a <code style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 12, background: "var(--bg-tag)", padding: "1px 5px", borderRadius: 4 }}>paths</code> block. ContextBrain will automatically extract all endpoints, auth mechanisms, and metadata. You can add business domain and ownership info to make the API easier to discover.
          </p>
          <div style={{ marginTop: 12, display: "flex", gap: 8 }}>
            <span style={{ fontSize: 11, padding: "3px 10px", borderRadius: 99, background: "var(--bg-tag)", color: "var(--text-tag)" }}>OpenAPI 3.0</span>
            <span style={{ fontSize: 11, padding: "3px 10px", borderRadius: 99, background: "var(--bg-tag)", color: "var(--text-tag)" }}>OpenAPI 3.1</span>
            <span style={{ fontSize: 11, padding: "3px 10px", borderRadius: 99, background: "var(--bg-tag)", color: "var(--text-tag)" }}>Swagger 2.0</span>
          </div>
        </div>
      )}
    </div>
  );
}

// --- Main App ---
export default function ContextBrain() {
  const [view, setView] = useState("chat");
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [catalog, setCatalog] = useState(INITIAL_CATALOG);
  const messagesEnd = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => { messagesEnd.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);
  useEffect(() => { if (view === "chat") inputRef.current?.focus(); }, [view]);

  const sendMessage = async (override) => {
    const msg = override || input.trim();
    if (!msg || loading) return;
    setInput("");
    setMessages(prev => [...prev, { role: "user", content: msg }]);
    setLoading(true);
    await new Promise(r => setTimeout(r, 1800));
    setMessages(prev => [...prev, {
      role: "assistant", content: MOCK_CHAT_RESPONSE,
      apis: catalog.slice(0, 2).map(a => ({ api: a, endpoints: a.endpoints, annotations: a.annotations, relevance_score: 0.92 - Math.random() * 0.2 })),
    }]);
    setLoading(false);
  };

  const handleIngest = (newApi) => {
    setCatalog(prev => [newApi, ...prev]);
  };

  const handleDelete = (id) => {
    setCatalog(prev => prev.filter(a => a.id !== id));
  };

  const SUGGESTIONS = [
    "Which API checks member eligibility?",
    "How do I look up a claim status?",
    "Find providers near a ZIP code",
    "Does behavioral health need prior auth?",
  ];

  const navItems = [
    { id: "chat", icon: "💬", label: "Discovery Chat" },
    { id: "catalog", icon: "📚", label: "API Catalog" },
    { id: "upload", icon: "📤", label: "Upload Spec" },
  ];

  return (
    <div style={{
      "--bg-main": "#0C0E14", "--bg-sidebar": "#12141D", "--bg-card": "#181B28", "--bg-input": "#181B28",
      "--bg-tag": "#232740", "--bg-annotation": "#161929", "--border-main": "#232740", "--border-card": "#282C42",
      "--border-subtle": "#1E2235", "--text-primary": "#E8E9EE", "--text-secondary": "#A8AAB8", "--text-muted": "#5E6178",
      "--text-tag": "#9294A8", "--accent": "#6366F1", "--accent-hover": "#818CF8",
      fontFamily: "'IBM Plex Sans', -apple-system, BlinkMacSystemFont, sans-serif",
      display: "flex", height: "100vh", width: "100vw", background: "var(--bg-main)", color: "var(--text-primary)", overflow: "hidden",
    }}>
      {/* Sidebar */}
      <div style={{ width: 220, background: "var(--bg-sidebar)", borderRight: "1px solid var(--border-main)", display: "flex", flexDirection: "column", flexShrink: 0 }}>
        <div style={{ padding: "20px 16px 16px", borderBottom: "1px solid var(--border-main)" }}>
          <h1 style={{ margin: 0, fontSize: 20, fontWeight: 800, letterSpacing: "-0.03em", display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", width: 28, height: 28, borderRadius: 8, background: "linear-gradient(135deg, #6366F1, #8B5CF6)", fontSize: 16 }}>🧠</span>
            ContextBrain
          </h1>
          <p style={{ margin: "6px 0 0", fontSize: 11, color: "var(--text-muted)", letterSpacing: "0.02em" }}>AI-Powered Context Discovery</p>
        </div>
        <nav style={{ padding: "12px 8px", display: "flex", flexDirection: "column", gap: 2 }}>
          {navItems.map(item => (
            <button key={item.id} onClick={() => setView(item.id)} style={{
              display: "flex", alignItems: "center", gap: 10, padding: "10px 12px", borderRadius: 8,
              background: view === item.id ? "var(--bg-card)" : "transparent",
              border: view === item.id ? "1px solid var(--border-card)" : "1px solid transparent",
              color: view === item.id ? "var(--text-primary)" : "var(--text-secondary)",
              cursor: "pointer", fontSize: 13, fontWeight: 500, textAlign: "left", width: "100%", transition: "all 0.15s", fontFamily: "inherit",
            }}>
              <span style={{ fontSize: 15 }}>{item.icon}</span> {item.label}
              {item.id === "catalog" && <span style={{ marginLeft: "auto", fontSize: 11, color: "var(--text-muted)", background: "var(--bg-tag)", padding: "1px 7px", borderRadius: 99 }}>{catalog.length}</span>}
            </button>
          ))}
        </nav>
        <div style={{ marginTop: "auto", padding: "16px 12px", borderTop: "1px solid var(--border-main)" }}>
          <p style={{ fontSize: 10, color: "var(--text-muted)", margin: "0 0 10px", textTransform: "uppercase", letterSpacing: "0.08em", fontWeight: 600 }}>Try asking</p>
          {["eligibility check", "claims status", "provider search", "prior auth"].map(q => (
            <button key={q} onClick={() => { setView("chat"); setTimeout(() => sendMessage(q), 100); }}
              style={{ display: "block", fontSize: 12, color: "var(--accent)", background: "none", border: "none", cursor: "pointer", padding: "5px 0", textAlign: "left", fontWeight: 500, fontFamily: "inherit" }}>
              → {q}
            </button>
          ))}
        </div>
      </div>

      {/* Main Content */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>

        {/* Chat View */}
        {view === "chat" && (
          <>
            <div style={{ flex: 1, overflowY: "auto", padding: "20px 28px" }}>
              {messages.length === 0 ? (
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100%", gap: 12 }}>
                  <div style={{ width: 56, height: 56, borderRadius: 16, background: "linear-gradient(135deg, #6366F1, #8B5CF6)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 28, boxShadow: "0 8px 32px rgba(99,102,241,0.25)" }}>🧠</div>
                  <h2 style={{ margin: "8px 0 0", fontSize: 24, fontWeight: 800, letterSpacing: "-0.02em" }}>What API do you need?</h2>
                  <p style={{ margin: 0, fontSize: 14, color: "var(--text-muted)", textAlign: "center", maxWidth: 440, lineHeight: 1.5 }}>
                    Ask in plain English. I'll search {catalog.length} APIs in the catalog and share tips from other developers.
                  </p>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 8, justifyContent: "center", maxWidth: 560, marginTop: 12 }}>
                    {SUGGESTIONS.map(s => (
                      <button key={s} onClick={() => sendMessage(s)} style={{ fontSize: 12, padding: "8px 16px", borderRadius: 99, background: "var(--bg-card)", border: "1px solid var(--border-card)", color: "var(--text-secondary)", cursor: "pointer", fontWeight: 500, fontFamily: "inherit" }}>
                        {s}
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                <>
                  {messages.map((msg, i) => <ChatMessage key={i} msg={msg} />)}
                  {loading && (
                    <div style={{ display: "flex", gap: 12, padding: "14px 0", alignItems: "center" }}>
                      <div style={{ width: 32, height: 32, borderRadius: "50%", background: "linear-gradient(135deg, #6366F1, #8B5CF6)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14, color: "#fff" }}>🧠</div>
                      <span style={{ fontSize: 13, color: "var(--text-muted)" }}>Searching {catalog.length} APIs</span>
                      <div style={{ display: "flex", gap: 5 }}>
                        {[0, 1, 2].map(i => <div key={i} style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--accent)", animation: `pulse 1.4s ease-in-out ${i * 0.2}s infinite` }} />)}
                      </div>
                    </div>
                  )}
                  <div ref={messagesEnd} />
                </>
              )}
            </div>
            <div style={{ padding: "12px 28px 20px", borderTop: "1px solid var(--border-main)" }}>
              <div style={{ display: "flex", gap: 8 }}>
                <input ref={inputRef} value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === "Enter" && !e.shiftKey && sendMessage()}
                  placeholder="Ask about an API...  e.g. 'Which API checks member eligibility?'"
                  style={{ flex: 1, padding: "12px 18px", borderRadius: 10, border: "1px solid var(--border-card)", background: "var(--bg-input)", color: "var(--text-primary)", fontSize: 14, outline: "none", fontFamily: "inherit" }} />
                <button onClick={() => sendMessage()} disabled={loading || !input.trim()} style={{
                  padding: "12px 22px", borderRadius: 10, background: loading || !input.trim() ? "var(--bg-tag)" : "var(--accent)",
                  color: "#fff", border: "none", cursor: loading ? "not-allowed" : "pointer", fontSize: 14, fontWeight: 700, fontFamily: "inherit",
                }}>{loading ? "..." : "Send"}</button>
              </div>
            </div>
          </>
        )}

        {/* Catalog View */}
        {view === "catalog" && (
          <div style={{ flex: 1, overflowY: "auto", padding: "24px 28px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
              <div>
                <h2 style={{ margin: 0, fontSize: 22, fontWeight: 800, letterSpacing: "-0.02em" }}>API Catalog</h2>
                <p style={{ margin: "4px 0 0", fontSize: 13, color: "var(--text-muted)" }}>{catalog.length} APIs registered</p>
              </div>
              <button onClick={() => setView("upload")} style={{ padding: "8px 16px", borderRadius: 8, background: "var(--accent)", border: "none", color: "#fff", fontSize: 12, fontWeight: 700, cursor: "pointer", fontFamily: "inherit", display: "flex", alignItems: "center", gap: 6 }}>
                <span>📤</span> Upload Spec
              </button>
            </div>
            {catalog.length === 0 ? (
              <div style={{ textAlign: "center", padding: 40, color: "var(--text-muted)" }}>
                <p style={{ fontSize: 36 }}>📭</p>
                <p>No APIs yet.</p>
                <button onClick={() => setView("upload")} style={{ marginTop: 8, color: "var(--accent)", background: "none", border: "none", cursor: "pointer", fontSize: 14, fontWeight: 600, fontFamily: "inherit" }}>Upload your first spec →</button>
              </div>
            ) : (
              catalog.map(a => <ApiCard key={a.id} result={a} onDelete={handleDelete} />)
            )}
          </div>
        )}

        {/* Upload View */}
        {view === "upload" && <UploadPanel onIngest={handleIngest} />}
      </div>

      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700;800&family=IBM+Plex+Mono:wght@400;500;700&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }
        ::-webkit-scrollbar { width: 5px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: var(--border-main); border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: #3A3E55; }
        @keyframes pulse { 0%, 100% { opacity: 0.25; transform: scale(1); } 50% { opacity: 1; transform: scale(1.3); } }
        input::placeholder, textarea::placeholder { color: var(--text-muted); }
        input:focus, textarea:focus, select:focus { border-color: var(--accent) !important; outline: none; }
        button:hover:not(:disabled) { filter: brightness(1.1); }
        select option { background: #181B28; color: #E8E9EE; }
        code { font-family: 'IBM Plex Mono', monospace; }
      `}</style>
    </div>
  );
}
