// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
/* ResponsibleAI shared app shell — sidebar/topbar injection, theme toggle,
   auth token storage, fetch helper with auth header + toasts.
   Self-contained, no external dependencies. Loaded by every page. */
(function (global) {
  "use strict";

  // Labels are i18n keys (resolved via RAI.i18n.t at render time), not
  // literal English text -- see static/js/i18n.js and static/locales/*.json.
  const NAV = [
    { groupKey: "nav.group.overview", items: [
      { id: "overview", labelKey: "nav.overview", href: "/" },
    ]},
    { groupKey: "nav.group.evaluate", items: [
      { id: "evaluate", labelKey: "nav.evaluate", href: "/evaluate" },
      { id: "guardrails", labelKey: "nav.guardrails", href: "/guardrails" },
      { id: "hallucination", labelKey: "nav.hallucination", href: "/hallucination" },
      { id: "eval", labelKey: "nav.eval", href: "/eval" },
      { id: "redteam", labelKey: "nav.redteam", href: "/redteam" },
    ]},
    { groupKey: "nav.group.cost_trust", items: [
      { id: "cost", labelKey: "nav.cost", href: "/cost" },
      { id: "router", labelKey: "nav.router", href: "/router" },
      { id: "trust-scores", labelKey: "nav.trust_scores", href: "/trust-scores" },
      { id: "leaderboard", labelKey: "nav.leaderboard", href: "/leaderboard" },
    ]},
    { groupKey: "nav.group.governance", items: [
      { id: "audit", labelKey: "nav.audit", href: "/audit" },
      { id: "incidents", labelKey: "nav.incidents", href: "/incidents" },
      { id: "incident-db", labelKey: "nav.incident_db", href: "/incident-db" },
      { id: "webhooks", labelKey: "nav.webhooks", href: "/webhooks-manage" },
    ]},
    { groupKey: "nav.group.account", items: [
      { id: "organizations", labelKey: "nav.organizations", href: "/organizations" },
      { id: "billing", labelKey: "nav.billing", href: "/billing" },
      { id: "settings", labelKey: "nav.settings", href: "/settings" },
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

  const BRAND_KEY = "rai_brand_cache";

  const branding = {
    // Cached in sessionStorage so every page nav doesn't re-fetch it, but
    // never stale across a real deploy since sessionStorage clears per tab
    // session. Falls back to the default name on any fetch failure —
    // white-labeling is cosmetic, never a reason to break page load.
    async get() {
      const cached = sessionStorage.getItem(BRAND_KEY);
      if (cached) {
        try { return JSON.parse(cached); } catch (e) { /* fall through */ }
      }
      try {
        const res = await fetch("/api/branding");
        const data = await res.json();
        sessionStorage.setItem(BRAND_KEY, JSON.stringify(data));
        return data;
      } catch (e) {
        return { brand_name: "ResponsibleAI", logo_url: "" };
      }
    },
    apply(data) {
      if (data.brand_name && data.brand_name !== "ResponsibleAI") {
        document.title = document.title.replace(/^ResponsibleAI/, data.brand_name);
      }
      const brandEl = document.querySelector(".brand");
      if (!brandEl) return;
      if (data.logo_url) {
        brandEl.innerHTML = '<img src="' + data.logo_url + '" alt="' + data.brand_name + '" class="brand-logo" />';
      } else if (data.brand_name) {
        brandEl.textContent = data.brand_name;
      }
    },
  };

  function renderChrome(activeId) {
    const t = global.RAI.i18n.t;
    const locale = global.RAI.i18n.getLocale();

    const shellEl = document.getElementById("rai-shell");
    if (!shellEl) return;

    const navHtml = NAV.map(function (group) {
      const items = group.items.map(function (item) {
        const cls = "rai-nav-item" + (item.id === activeId ? " active" : "");
        return '<a class="' + cls + '" href="' + item.href + '"><span class="dot"></span>' + t(item.labelKey) + "</a>";
      }).join("");
      return '<div class="rai-nav-group"><div class="rai-nav-label">' + t(group.groupKey) + "</div>" + items + "</div>";
    }).join("");

    const localeOptions = global.RAI.i18n.SUPPORTED_LOCALES.map(function (code) {
      const selected = code === locale ? " selected" : "";
      return '<option value="' + code + '"' + selected + ">" + code.toUpperCase() + "</option>";
    }).join("");

    const loggedIn = auth.isLoggedIn();
    const topbarActionsHtml =
      '<select class="btn btn-sm" id="rai-locale-select" aria-label="' + t("topbar.locale_label") + '" title="' + t("topbar.locale_label") + '">' + localeOptions + "</select>" +
      '<button class="btn btn-sm" id="rai-theme-toggle" title="' + t("topbar.toggle_theme") + '">' + t("topbar.toggle_theme") + "</button>" +
      (loggedIn
        ? '<button class="btn btn-sm" id="rai-logout">' + t("topbar.logout") + "</button>"
        : '<a class="btn btn-sm" href="/signup">' + t("topbar.signup") + '</a><a class="btn btn-sm btn-primary" href="/login">' + t("topbar.login") + "</a>");

    const existingApp = shellEl.querySelector(".rai-app");

    if (!existingApp) {
      // First render for this page load: build the full chrome, including
      // an empty #rai-page-content that the page's own inline <script>
      // fills in synchronously right after calling RAI.shell(activeId) --
      // that classic synchronous contract must keep working, so this
      // branch runs entirely synchronously (see initSync() in i18n.js).
      shellEl.innerHTML =
        '<div class="rai-app">' +
        '<aside class="rai-sidebar" id="rai-sidebar">' +
        '<div class="brand">ResponsibleAI</div>' +
        "<nav>" + navHtml + "</nav>" +
        "</aside>" +
        '<div class="rai-main">' +
        '<header class="rai-topbar">' +
        '<button class="btn btn-icon" id="rai-nav-toggle" aria-label="' + t("topbar.toggle_nav") + '" title="' + t("topbar.toggle_nav") + '">&#9776;</button>' +
        '<div class="actions">' + topbarActionsHtml + "</div>" +
        "</header>" +
        '<div class="rai-content" id="rai-page-content"></div>' +
        "</div>" +
        "</div>";

      document.getElementById("rai-nav-toggle").addEventListener("click", function () {
        document.getElementById("rai-sidebar").classList.toggle("open");
      });
    } else {
      // Re-render triggered by a locale switch: replace only the sidebar
      // nav and topbar actions, never #rai-page-content -- so an in-
      // progress form fill or loaded results table survives a language
      // change instead of being silently wiped out.
      existingApp.querySelector(".rai-sidebar nav").innerHTML = navHtml;
      const toggleBtn = existingApp.querySelector("#rai-nav-toggle");
      if (toggleBtn) {
        toggleBtn.setAttribute("aria-label", t("topbar.toggle_nav"));
        toggleBtn.setAttribute("title", t("topbar.toggle_nav"));
      }
      existingApp.querySelector(".rai-topbar .actions").innerHTML = topbarActionsHtml;
    }

    document.getElementById("rai-theme-toggle").addEventListener("click", theme.toggle);
    document.getElementById("rai-locale-select").addEventListener("change", function (e) {
      global.RAI.i18n.setLocale(e.target.value).then(function () {
        renderChrome(activeId);
      });
    });
    const logoutBtn = document.getElementById("rai-logout");
    if (logoutBtn) {
      logoutBtn.addEventListener("click", function () {
        auth.clearToken();
        window.location.href = "/login";
      });
    }
  }

  function shell(activeId) {
    theme.init();
    const i18n = global.RAI.i18n;
    // Synchronous: the default locale's catalog is embedded (no fetch), so
    // this always resolves to a real, correctly-translated chrome on the
    // very first paint -- never a flash of raw "nav.overview"-style keys.
    // If the visitor's actual preferred locale isn't the default and its
    // catalog isn't cached yet, this falls back to the default for now.
    i18n.initSync();
    renderChrome(activeId);

    // Upgrade to the visitor's real preferred locale asynchronously if it
    // differs from what initSync() could resolve synchronously. This never
    // touches #rai-page-content (see the re-render branch above), so
    // whatever the page's own script has already put there survives.
    const detected = i18n.detectLocale();
    if (detected !== i18n.getLocale()) {
      i18n.setLocale(detected).then(function () {
        renderChrome(activeId);
      });
    }

    branding.get().then(branding.apply);
  }

  // Merge into any existing global.RAI (i18n.js, loaded first on every
  // page, already attached .i18n there) rather than replacing it outright.
  global.RAI = Object.assign(global.RAI || {}, { shell, theme, auth, toast, fetchJSON, branding, NAV });
})(window);
