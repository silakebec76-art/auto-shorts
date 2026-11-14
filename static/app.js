const $ = (s, el = document) => el.querySelector(s);
let status = null;
let currentId = null;
let pollTimer = null;
let tiktokOptions = null; // options de confidentialité proposées par TikTok
const cards = new Map(); // "jobId:index" -> élément

const PRIVACY_LABELS = {
  PUBLIC_TO_EVERYONE: "Public",
  MUTUAL_FOLLOW_FRIENDS: "Amis",
  FOLLOWER_OF_CREATOR: "Abonnés",
  SELF_ONLY: "Moi uniquement (privé)",
};

function toast(msg) {
  const t = document.createElement("div");
  t.className = "toast";
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 4000);
}

async function api(path, opts = {}) {
  const res = await fetch(path, opts);
  let data = null;
  try { data = await res.json(); } catch { /* vide */ }
  if (!res.ok) throw new Error((data && data.detail) || `Erreur ${res.status}`);
  return data;
}

// ------------------------------------------------------------ comptes

function renderAccount(id, name, s) {
  const el = $(id);
  el.className = "account" + (s.connected ? " on" : "");
  if (s.connected) {
    el.innerHTML = `<span class="dot"></span>${name} connecté · <button data-off>déconnecter</button>`;
    $("[data-off]", el).onclick = async () => {
      await api(`/auth/${name.toLowerCase()}/disconnect`, { method: "POST" });
      loadStatus();
    };
  } else {
    el.innerHTML = `<span class="dot"></span>${name} : <a href="/auth/${name.toLowerCase()}/start">connecter</a>`;
  }
}

async function loadStatus() {
  status = await api("/api/status");
  renderAccount("#acc-youtube", "YouTube", status.youtube);
  renderAccount("#acc-tiktok", "TikTok", status.tiktok);
  const hint = $("#ai-hint");
  if (status.ai) {
    hint.className = "hint";
    hint.textContent = "L'IA choisit les meilleurs moments et écrit les titres, descriptions et hashtags.";
  } else {
    hint.className = "hint warn";
    hint.textContent = "⚠️ Pas de clé IA (ANTHROPIC_API_KEY) : les moments seront choisis en mode simple. Ajoute ta clé dans le fichier .env pour de meilleurs résultats.";
  }
  if (status.tiktok.connected && !tiktokOptions) {
    try {
      const info = await api("/api/tiktok/creator");
      tiktokOptions = info.privacy_level_options || ["SELF_ONLY"];
    } catch (e) {
      tiktokOptions = ["SELF_ONLY"];
    }
    document.querySelectorAll(".tt-privacy").forEach(fillTiktokSelect);
  }
}

function fillTiktokSelect(sel) {
  const opts = tiktokOptions || ["SELF_ONLY"];
  if (sel.options.length === opts.length) return;
  sel.innerHTML = opts.map(o => `<option value="${o}">${PRIVACY_LABELS[o] || o}</option>`).join("");
}

// ------------------------------------------------------------ nouveau projet

document.querySelectorAll(".tab").forEach(btn => btn.onclick = () => {
  document.querySelectorAll(".tab").forEach(b => b.classList.toggle("active", b === btn));
  document.querySelectorAll(".tab-pane").forEach(p => p.classList.toggle("hidden", p.dataset.pane !== btn.dataset.tab));
});
$("#count").oninput = e => $("#count-val").textContent = e.target.value;

$("#form").onsubmit = async e => {
  e.preventDefault();
  const btn = $("button[type=submit]", e.target);
  const mode = $(".tab.active").dataset.tab;
  const count = +$("#count").value;
  const language = $("#language").value;
  btn.disabled = true;
  try {
    let job;
    if (mode === "link") {
      const url = $("#url").value.trim();
      if (!url) throw new Error("Colle d'abord un lien YouTube");
      job = await api("/api/jobs", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url, count, language: language || null }),
      });
      $("#url").value = "";
    } else {
      const f = $("#file").files[0];
      if (!f) throw new Error("Choisis d'abord un fichier vidéo");
      const fd = new FormData();
      fd.append("file", f); fd.append("count", count); fd.append("language", language);
      toast("Envoi du fichier…");
      job = await api("/api/jobs/upload", { method: "POST", body: fd });
    }
    await loadJobs();
    openJob(job.id);
  } catch (err) {
    toast(err.message);
  } finally {
    btn.disabled = false;
  }
};

// ------------------------------------------------------------ liste des projets

async function loadJobs() {
  const list = await api("/api/jobs");
  const box = $("#jobs");
  if (!list.length) { box.innerHTML = `<p class="hint">Aucun projet pour l'instant.</p>`; return; }
  box.innerHTML = "";
  for (const j of list) {
    const row = document.createElement("div");
    row.className = "job" + (j.id === currentId ? " active" : "");
    const date = new Date(j.created_at * 1000).toLocaleString("fr-FR");
    const icon = { done: "✅", error: "❌" }[j.status] || "⏳";
    row.innerHTML = `<div>${icon} <b></b><br><small>${date} · ${j.clips.length} shorts</small></div><button class="del" title="Supprimer">🗑️</button>`;
    $("b", row).textContent = j.title || j.url;
    row.onclick = () => openJob(j.id);
    $(".del", row).onclick = async ev => {
      ev.stopPropagation();
      if (!confirm("Supprimer ce projet et ses shorts ?")) return;
      await api(`/api/jobs/${j.id}`, { method: "DELETE" });
      if (currentId === j.id) { currentId = null; $("#current").innerHTML = ""; }
      loadJobs();
    };
    box.appendChild(row);
  }
}

// ------------------------------------------------------------ projet ouvert

function openJob(id) {
  if (currentId !== id) {
    currentId = id;
    cards.clear();
    $("#current").innerHTML = "";
  }
  clearTimeout(pollTimer);
  refreshJob();
  loadJobs();
  $("#current").scrollIntoView({ behavior: "smooth" });
}

async function refreshJob() {
  if (!currentId) return;
  let job;
  try { job = await api(`/api/jobs/${currentId}`); } catch { return; }
  renderJob(job);
  const busy = !["done", "error"].includes(job.status) ||
    job.clips.some(c => c.youtube.status === "uploading" || c.tiktok.status === "uploading");
  if (busy) pollTimer = setTimeout(refreshJob, 2000);
  else if (job.status === "done" || job.status === "error") loadJobs();
}

function renderJob(job) {
  const root = $("#current");
  if (!root.firstChild) {
    root.innerHTML = `<div class="card"><h2></h2><div class="progress-wrap"><div class="progress"><div></div></div></div>
      <p class="status-msg"></p><button class="retry hidden">🔁 Relancer</button><div class="clips"></div></div>`;
    $(".retry", root).onclick = async () => {
      await api(`/api/jobs/${job.id}/retry`, { method: "POST" });
      cards.clear(); $(".clips", root).innerHTML = "";
      refreshJob();
    };
  }
  $("h2", root).textContent = job.title || job.url;
  $(".progress > div", root).style.width = `${Math.round(job.progress * 100)}%`;
  $(".progress-wrap", root).classList.toggle("hidden", job.status === "done");
  const msg = $(".status-msg", root);
  msg.textContent = job.message;
  msg.classList.toggle("err", job.status === "error");
  $(".retry", root).classList.toggle("hidden", job.status !== "error");

  const grid = $(".clips", root);
  for (const clip of job.clips) {
    const key = `${job.id}:${clip.index}`;
    let card = cards.get(key);
    if (!card) {
      card = makeCard(job.id, clip);
      cards.set(key, card);
      grid.appendChild(card);
    }
    updateCard(card, job.id, clip);
  }
}

function fmt(t) {
  const m = Math.floor(t / 60), s = Math.floor(t % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

function makeCard(jobId, clip) {
  const card = $("#clip-tpl").content.firstElementChild.cloneNode(true);
  $(".title", card).value = clip.title;
  $(".description", card).value = clip.description;
  $(".hashtags", card).value = clip.hashtags.map(h => "#" + h).join(" ");
  $(".reason", card).textContent = `💡 ${clip.reason}`;
  $(".badge", card).textContent = `#${clip.index + 1} · ${fmt(clip.start)} → ${fmt(clip.end)} · ${Math.round(clip.end - clip.start)} s`;
  fillTiktokSelect($(".tt-privacy", card));

  const save = async (quiet) => {
    const body = {
      title: $(".title", card).value,
      description: $(".description", card).value,
      hashtags: $(".hashtags", card).value.split(/[\s,]+/).filter(Boolean),
    };
    await api(`/api/jobs/${jobId}/clips/${clip.index}`, {
      method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    if (!quiet) toast("Enregistré ✔");
  };
  $(".save", card).onclick = () => save(false).catch(e => toast(e.message));

  $(".yt-btn", card).onclick = async () => {
    if (!status.youtube.connected) return toast("Connecte d'abord YouTube (en haut à droite).");
    try {
      await save(true);
      await api(`/api/jobs/${jobId}/clips/${clip.index}/youtube`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ privacy: $(".yt-privacy", card).value }),
      });
      refreshJobSoon();
    } catch (e) { toast(e.message); }
  };
  $(".tt-btn", card).onclick = async () => {
    if (!status.tiktok.connected) return toast("Connecte d'abord TikTok (en haut à droite).");
    try {
      await save(true);
      await api(`/api/jobs/${jobId}/clips/${clip.index}/tiktok`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ privacy_level: $(".tt-privacy", card).value }),
      });
      refreshJobSoon();
    } catch (e) { toast(e.message); }
  };
  return card;
}

function refreshJobSoon() {
  clearTimeout(pollTimer);
  pollTimer = setTimeout(refreshJob, 500);
}

function publishStatus(el, s, name) {
  el.className = "";
  if (!s || !s.status) { el.textContent = ""; return; }
  if (s.status === "uploading") el.textContent = "⏳ Envoi en cours…";
  else if (s.status === "error") { el.className = "err"; el.textContent = "❌ " + s.error; }
  else if (s.status === "done") {
    el.className = "ok";
    if (s.url) el.innerHTML = `✅ Publié · <a href="${s.url}" target="_blank" rel="noopener">voir</a>`;
    else el.textContent = s.tiktok_status === "PUBLISH_COMPLETE" ? `✅ Publié sur ${name}` : `✅ Envoyé sur ${name} (en cours de traitement)`;
  }
}

function updateCard(card, jobId, clip) {
  const player = $(".player", card);
  const video = $("video", card);
  if (clip.file) {
    const src = `/media/${jobId}/${clip.file}`;
    if (!video.getAttribute("src")) video.setAttribute("src", src);
    video.classList.remove("hidden");
    $(".placeholder", player)?.remove();
    const dl = $(".download", card);
    dl.href = src; dl.classList.remove("hidden");
  } else {
    video.classList.add("hidden");
    $(".download", card).classList.add("hidden");
    if (!$(".placeholder", player)) {
      const ph = document.createElement("div");
      ph.className = "placeholder";
      ph.textContent = "Montage en cours…";
      player.prepend(ph);
    }
  }
  const ready = !!clip.file;
  const ytBusy = clip.youtube.status === "uploading", ttBusy = clip.tiktok.status === "uploading";
  $(".yt-btn", card).disabled = !ready || ytBusy;
  $(".tt-btn", card).disabled = !ready || ttBusy;
  publishStatus($(".yt-status", card), clip.youtube, "YouTube");
  publishStatus($(".tt-status", card), clip.tiktok, "TikTok");
}

// ------------------------------------------------------------ démarrage

(async function init() {
  const params = new URLSearchParams(location.search);
  if (params.get("connected")) {
    toast(`Compte ${params.get("connected") === "youtube" ? "YouTube" : "TikTok"} connecté ✔`);
    history.replaceState(null, "", "/");
  }
  await loadStatus();
  await loadJobs();
  const list = await api("/api/jobs");
  if (list.length) openJob(list[0].id);
})();
