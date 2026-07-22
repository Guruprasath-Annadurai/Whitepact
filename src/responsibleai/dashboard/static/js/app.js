/* ResponsibleAI shared app shell — sidebar/topbar injection, theme toggle,
   auth token storage, fetch helper with auth header + toasts.
   Self-contained, no external dependencies. Loaded by every page. */
(function (global) {
  "use strict";

  const NAV = [
    { group: "Overview", items: [
      { id: "overview", label: "Dashboard", href: "/" },
    ]},
    { group: "Evaluate", items: [
      { id: "evaluate", label: "Evaluate Model", href: "/evaluate" },
      { id: "guardrails", label: "Guardrails", href: "/guardrails" },
      { id: "hallucination", label: "Hallucination", href: "/hallucination" },
      { id: "eval", label: "Compare & Benchmark", href: "/eval" },
      { id: "redteam", label: "Red Team", href: "/redteam" },
    ]},
    { group: "Cost & Trust", items: [
      { id: "cost", label: "Cost Intelligence", href: "/cost" },
      { id: "router", label: "Model Router", href: "/router" },
      { id: "trust-scores", label: "Trust Scores", href: "/trust-scores" },
      { id: "leaderboard", label: "Leaderboard", href: "/leaderboard" },
    ]},
    { group: "Governance", items: [
      { id: "audit", label: "Audit Log", href: "/audit" },
      { id: "incidents", label: "Incidents", href: "/incidents" },
      { id: "incident-db", label: "Incident Database", href: "/incident-db" },
      { id: "webhooks", label: "Webhooks", href: "/webhooks-manage" },
    ]},
    { group: "Account", items: [
      { id: "organizations", label: "Organizations & Access", href: "/organizations" },
      { id: "billing", label: "Billing", href: "/billing" },
      { id: "settings", label: "Settings", href: "/settings" },
    ]},
  ];

  const THEME_KEY = "rai_theme";
  const TOKEN_KEY = "rai_api_key";

  const theme = {
    init() {
      const saved = localStorage.getItem(THEME_KEY);
      if (saved === "dark" || saved === "light") {
        document.documentElement.setAttribute("data-theme", saved);
      }
    },
    toggle() {
      const current = document.documentElement.getAttribute("data-theme")
        || (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
      const next = current === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      localStorage.setItem(THEME_KEY, next);
    },
  };

  const auth = {
    getToken() { return localStorage.getItem(TOKEN_KEY) || ""; },
    setToken(token) { localStorage.setItem(TOKEN_KEY, token); },
    clearToken() { localStorage.removeItem(TOKEN_KEY); },
    isLoggedIn() { return !!auth.getToken(); },
    headers(extra) {
      const h = Object.assign({}, extra || {});
      const token = auth.getToken();
      if (token) h["Authorization"] = "Bearer " + token;
      return h;
    },
  };

  function toast(message, kind) {
    let host = document.getElementById("rai-toast-host");
    if (!host) {
      host = document.createElement("div");
      host.id = "rai-toast-host";
      document.body.appendChild(host);
    }
    const el = document.createElement("div");
    el.className = "rai-toast" + (kind ? " " + kind : "");
    el.textContent = message;
    host.appendChild(el);
    setTimeout(function () { el.remove(); }, 5000);
  }

  async function fetchJSON(url, options) {
    options = options || {};
    const headers = auth.headers(Object.assign(
      { "Content-Type": "application/json" }, options.headers || {},
    ));
    const res = await fetch(url, Object.assign({}, options, { headers }));
    let body = null;
    const text = await res.text();
    if (text) {
      try { body = JSON.parse(text); } catch (e) { body = text; }
    }
    if (!res.ok) {
      if (res.status === 401 && !options.skipAuthRedirect) {
        const next = encodeURIComponent(window.location.pathname + window.location.search);
        window.location.href = "/login?next=" + next;
      }
      const message = (body && (body.message || body.detail || body.error)) || ("HTTP " + res.status);
      const err = new Error(typeof message === "string" ? message : JSON.stringify(message));
      err.status = res.status;
      err.body = body;
      throw err;
    }
    return body;
  }

  function shell(activeId) {
    theme.init();

    const shellEl = document.getElementById("rai-shell");
    if (!shellEl) return;

    const navHtml = NAV.map(function (group) {
      const items = group.items.map(function (item) {
        const cls = "rai-nav-item" + (item.id === activeId ? " active" : "");
        return '<a class="' + cls + '" href="' + item.href + '"><span class="dot"></span>' + item.label + "</a>";
      }).join("");
      return '<div class="rai-nav-group"><div class="rai-nav-label">' + group.group + "</div>" + items + "</div>";
    }).join("");

    const loggedIn = auth.isLoggedIn();
    shellEl.innerHTML =
      '<div class="rai-app">' +
      '<aside class="rai-sidebar" id="rai-sidebar">' +
      '<div class="brand">ResponsibleAI</div>' +
      "<nav>" + navHtml + "</nav>" +
      "</aside>" +
      '<div class="rai-main">' +
      '<header class="rai-topbar">' +
      '<button class="btn btn-icon" id="rai-nav-toggle" aria-label="Toggle navigation" title="Toggle navigation">&#9776;</button>' +
      '<div class="actions">' +
      '<button class="btn btn-sm" id="rai-theme-toggle" title="Toggle theme">Theme</button>' +
      (loggedIn
        ? '<button class="btn btn-sm" id="rai-logout">Logout</button>'
        : '<a class="btn btn-sm btn-primary" href="/login">Login</a>') +
      "</div>" +
      "</header>" +
      '<div class="rai-content" id="rai-page-content"></div>' +
      "</div>" +
      "</div>";

    document.getElementById("rai-theme-toggle").addEventListener("click", theme.toggle);
    document.getElementById("rai-nav-toggle").addEventListener("click", function () {
      document.getElementById("rai-sidebar").classList.toggle("open");
    });
    const logoutBtn = document.getElementById("rai-logout");
    if (logoutBtn) {
      logoutBtn.addEventListener("click", function () {
        auth.clearToken();
        window.location.href = "/login";
      });
    }
  }

  global.RAI = { shell, theme, auth, toast, fetchJSON, NAV };
})(window);
