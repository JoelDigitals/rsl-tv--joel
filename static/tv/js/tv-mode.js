/*
 * RSL Mediathek – Fernbedienungs-Modus für die RSL-TV-App (Smart-TV, Fire TV, Android TV).
 * Aktiv nur, wenn die Mediathek aus der App mit ?tv=1 geöffnet wurde (bleibt für die Sitzung aktiv).
 *  - Pfeiltasten bewegen eine sichtbare Auswahl über Links/Knöpfe (räumliche Navigation)
 *  - OK öffnet, Zurück geht eine Seite zurück, auf der Startseite zurück zum Live-Programm der App
 *  - Rote Taste: zurück zum Live-Programm
 *  - Auf Player-Seiten läuft das Video im Vollbild; ◀ ▶ / OK / Kanal± werden an den RSL-Player weitergereicht
 */
(function () {
  "use strict";
  var KEY_STORE = "rslTv", RETURN_STORE = "rslTvReturn", DEPTH_STORE = "rslTvDepth";
  var params = new URLSearchParams(location.search);
  var store = window.sessionStorage;

  try {
    if (params.get("tv") === "1") {
      store.setItem(KEY_STORE, "1");
      store.setItem(DEPTH_STORE, "0");
      if (params.get("return")) store.setItem(RETURN_STORE, params.get("return"));
    } else if (store.getItem(KEY_STORE) === "1") {
      var nav = performance.getEntriesByType && performance.getEntriesByType("navigation")[0];
      if (!nav || nav.type === "navigate") store.setItem(DEPTH_STORE, String(Number(store.getItem(DEPTH_STORE) || 0) + 1));
    }
    if (store.getItem(KEY_STORE) !== "1") return;
  } catch (e) {
    if (params.get("tv") !== "1") return;
  }

  var returnUrl = (function () { try { return store.getItem(RETURN_STORE); } catch (e) { return null; } })() || "https://tv.85-215-240-180.sslip.io/tv";
  document.documentElement.classList.add("tv-mode");

  var css = [
    ".tv-mode body{cursor:none}",
    ".tv-mode .mt-footer,.tv-mode .skip-link,.tv-mode .mt-search{display:none!important}",
    ".tv-mode .tv-focus{outline:4px solid #e11d48!important;outline-offset:4px;border-radius:12px;transform:scale(1.03);transition:transform .12s;position:relative;z-index:5}",
    ".tv-mode .tv-hint{position:fixed;left:50%;bottom:16px;transform:translateX(-50%);z-index:10000;background:rgba(0,0,0,.75);color:#fff;padding:8px 18px;border-radius:999px;font:600 15px/1.4 system-ui,sans-serif;pointer-events:none}",
    ".tv-mode.tv-playing .player{position:fixed!important;inset:0!important;z-index:9999!important;aspect-ratio:auto!important;border-radius:0!important;border:0!important;margin:0!important}",
    ".tv-mode.tv-playing body{overflow:hidden}"
  ].join("\n");
  var style = document.createElement("style");
  style.textContent = css;
  document.head.appendChild(style);

  var KEYS = {
    ArrowUp: "up", Up: "up", ArrowDown: "down", Down: "down", ArrowLeft: "left", Left: "left", ArrowRight: "right", Right: "right",
    Enter: "enter", Select: "enter", " ": "enter",
    Escape: "back", Esc: "back", Backspace: "back", BrowserBack: "back", GoBack: "back", XF86Back: "back",
    ColorF0Red: "red", Red: "red", r: "red", R: "red",
    ChannelUp: "next", MediaFastForward: "next", ChannelDown: "prev", MediaRewind: "prev", MediaPlayPause: "enter"
  };
  var CODES = { 38: "up", 40: "down", 37: "left", 39: "right", 13: "enter", 27: "back", 8: "back", 10009: "back", 461: "back", 4: "back", 403: "red", 183: "red", 427: "next", 428: "prev", 417: "next", 412: "prev", 415: "enter", 19: "enter" };

  function playerFrame() {
    return document.querySelector(".player iframe");
  }
  var playing = false;

  function depth() { try { return Number(store.getItem(DEPTH_STORE) || 0); } catch (e) { return 0; } }
  // Während ein Seitenwechsel läuft, keine weiteren Tasten (sonst zählt „Zurück“ doppelt).
  var leaving = false, leaveTimer = null;
  function setLeaving() {
    leaving = true;
    clearTimeout(leaveTimer);
    leaveTimer = setTimeout(function () { leaving = false; }, 15000); // Seitenwechsel gescheitert → wieder bedienbar
  }
  window.addEventListener("pageshow", function () { leaving = false; clearTimeout(leaveTimer); });
  function goLive() {
    setLeaving();
    try { store.removeItem(KEY_STORE); } catch (e) { /* egal */ }
    location.href = returnUrl;
  }
  function goBack() {
    var d = depth();
    if (d > 0) {
      setLeaving();
      try { store.setItem(DEPTH_STORE, String(d - 1)); } catch (e) { /* egal */ }
      history.back();
    } else {
      goLive();
    }
  }

  // ── Räumliche Navigation ──
  function focusables() {
    var list = document.querySelectorAll("main a[href], main button:not([disabled]), .mt-header a[href], [data-tv-focus]");
    var out = [];
    for (var i = 0; i < list.length; i++) {
      var el = list[i];
      if (el.closest(".mt-footer, .mt-search")) continue;
      var r = el.getBoundingClientRect();
      if (r.width < 4 || r.height < 4) continue;
      var cs = getComputedStyle(el);
      if (cs.visibility === "hidden" || cs.display === "none") continue;
      out.push(el);
    }
    return out;
  }
  var current = null;
  function setFocus(el) {
    if (!el) return;
    if (current) current.classList.remove("tv-focus");
    current = el;
    el.classList.add("tv-focus");
    try { el.focus({ preventScroll: true }); } catch (e) { /* egal */ }
    el.scrollIntoView({ block: "center", inline: "nearest", behavior: "smooth" });
  }
  function center(r) { return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; }
  function move(dir) {
    var items = focusables();
    if (!items.length) return;
    if (!current || items.indexOf(current) < 0) { setFocus(items[0]); return; }
    var from = current.getBoundingClientRect(), c = center(from), best = null, bestScore = Infinity;
    for (var i = 0; i < items.length; i++) {
      var el = items[i];
      if (el === current) continue;
      var r = el.getBoundingClientRect(), p = center(r);
      var dx = p.x - c.x, dy = p.y - c.y, primary, cross;
      if (dir === "left") { if (r.right > from.left + 2) continue; primary = -dx; cross = Math.abs(dy); }
      else if (dir === "right") { if (r.left < from.right - 2) continue; primary = dx; cross = Math.abs(dy); }
      else if (dir === "up") { if (r.bottom > from.top + 2) continue; primary = -dy; cross = Math.abs(dx); }
      else { if (r.top < from.bottom - 2) continue; primary = dy; cross = Math.abs(dx); }
      var score = primary + cross * 2.5;
      if (score < bestScore) { bestScore = score; best = el; }
    }
    if (best) setFocus(best);
  }
  function initialFocus() {
    var main = document.querySelector("main");
    var items = focusables();
    var first = items.filter(function (el) { return main && main.contains(el) && !el.closest(".breadcrumbs"); })[0] || items[0];
    setFocus(first);
  }

  // ── Player-Seiten: Vollbild, Tasten an den RSL-Player ──
  function sendToPlayer(key) {
    var f = playerFrame();
    if (f && f.contentWindow) f.contentWindow.postMessage({ type: "rsl-tv-key", key: key }, "*");
  }
  function preparePlayer() {
    var f = playerFrame();
    if (!f) return false;
    // Ton ein und Fernbedienungs-Modus im RSL-Player
    if (/\/mediathek\?/.test(f.src) && !/[?&]tv=1/.test(f.src)) f.src = f.src + "&tv=1&ton=1";
    document.documentElement.classList.add("tv-playing");
    playing = true;
    return true;
  }

  function hint(text) {
    var h = document.createElement("div");
    h.className = "tv-hint";
    h.textContent = text;
    document.body.appendChild(h);
    setTimeout(function () { h.remove(); }, 5000);
  }

  function handle(key) {
    if (leaving) return true;
    if (key === "red") { goLive(); return true; }
    if (key === "back") { goBack(); return true; }
    if (playing) {
      if (key === "left" || key === "right" || key === "enter" || key === "next" || key === "prev" || key === "up" || key === "down") sendToPlayer(key);
      return true;
    }
    if (key === "enter") {
      if (!current) { initialFocus(); return true; }
      // „Live-TV“-Links führen zurück zum Live-Programm der App
      var href = current.getAttribute("href") || "";
      if (href === "/" || href === "/live/" ) { goLive(); return true; }
      if (href && href.charAt(0) !== "#") setLeaving();
      current.click();
      return true;
    }
    if (key === "up" || key === "down" || key === "left" || key === "right") { move(key); return true; }
    return false;
  }

  window.addEventListener("keydown", function (e) {
    var key = KEYS[e.key] || CODES[e.keyCode];
    if (!key) return;
    var t = e.target;
    if (t && /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName) && key !== "back") return;
    if (handle(key)) { e.preventDefault(); e.stopPropagation(); }
  }, true);

  // Hat der Player-Frame den Fokus, schickt er Zurück/Rot per Nachricht hierher.
  window.addEventListener("message", function (e) {
    var f = playerFrame();
    if (!f || !e.data || e.data.type !== "rsl-tv-parent-key") return;
    try { if (new URL(f.src).origin !== e.origin) return; } catch (err) { return; }
    if (e.data.key === "back" || e.data.key === "red") handle(e.data.key);
  });

  // Schnittstelle für den Android-/Fire-TV-Wrapper (Zurück- und Sondertasten)
  window.rslTvBack = function () { goBack(); return true; };
  window.rslTvKey = function (name) {
    var map = { mediathek: "red", guide: "red", info: "up", mute: "enter" };
    handle(map[name] || name);
  };

  document.addEventListener("DOMContentLoaded", function () {
    if (preparePlayer()) hint("◀ ▶ spulen · OK Pause · Zurück zur Übersicht · Rot: Live-TV");
    else { initialFocus(); hint("Pfeiltasten auswählen · OK öffnen · Zurück · Rot: Live-TV"); }
  });
})();
