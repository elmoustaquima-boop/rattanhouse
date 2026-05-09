// ═══════════════════════════════════════════
// RATTAN HOUSE — JavaScript
// ═══════════════════════════════════════════

// ─── PANIER (localStorage) ───────────────────
function getPanier() {
  try { return JSON.parse(localStorage.getItem('rh_panier') || '[]'); } catch { return []; }
}
function savePanier(p) {
  localStorage.setItem('rh_panier', JSON.stringify(p));
  updatePanierBadge();
}
function updatePanierBadge() {
  const p = getPanier();
  const total = p.reduce((s, i) => s + (i.qty || 1), 0);
  const badge = document.getElementById('panierBadge');
  if (badge) {
    if (total > 0) { badge.textContent = total; badge.style.display = 'flex'; }
    else { badge.style.display = 'none'; }
  }
}
function ajouterAuPanier(id, nom, prix, matiere, image) {
  const p = getPanier();
  const idx = p.findIndex(i => i.id === id);
  if (idx >= 0) { p[idx].qty = (p[idx].qty || 1) + 1; }
  else { p.push({ id, nom, prix, matiere, image, qty: 1 }); }
  savePanier(p);
  showToast('✓ Ajouté au panier !');
}

// ─── ADMIN SESSION (pour afficher l'icône admin) ─
async function checkAdminSession() {
  try {
    const r = await fetch('/api/session-info');
    const d = await r.json();
    const adminLink = document.getElementById('adminLink');
    if (adminLink && d.logged_in && d.user_role === 'admin') {
      adminLink.style.display = 'flex';
    }
  } catch(e) {}
}

// ─── MOBILE MENU ────────────────────────────
function toggleMobileMenu() {
  document.getElementById('navLinks').classList.toggle('open');
  document.getElementById('hamburger').classList.toggle('open');
}

// ─── TOAST ──────────────────────────────────
function showToast(msg, type = 'success') {
  const t = document.getElementById('toast');
  if (!t) return;
  t.textContent = (type === 'success' ? '✓ ' : '✕ ') + msg;
  t.className = 'toast show ' + type;
  setTimeout(() => { t.className = 'toast'; }, 4000);
}

// ─── FILE PREVIEW ────────────────────────────
function previewFile(input) {
  const drop = document.getElementById('fileDropContent');
  if (!drop) return;
  if (input.files && input.files[0]) {
    const r = new FileReader();
    r.onload = e => {
      drop.innerHTML = `<img src="${e.target.result}" style="max-height:120px;border-radius:8px;margin:0 auto 8px;display:block">
        <p style="font-size:12px;color:var(--text-light)">${input.files[0].name}</p>`;
    };
    r.readAsDataURL(input.files[0]);
  }
}

// ─── ADMIN ───────────────────────────────────
async function supprimerProduit(id) {
  if (!confirm('Supprimer ce produit ?')) return;
  const btn = document.querySelector(`button[onclick="supprimerProduit(${id})"]`);
  if (btn) { btn.disabled = true; btn.textContent = 'Suppression...'; }
  try {
    const r = await fetch(`/admin/supprimer-produit/${id}`, { method: 'DELETE' });
    const d = await r.json();
    if (d.success) { showToast('Produit supprimé'); setTimeout(() => location.reload(), 800); }
    else { showToast('Erreur lors de la suppression', 'error'); if (btn) { btn.disabled = false; btn.textContent = 'Supprimer'; } }
  } catch { showToast('Erreur réseau', 'error'); if (btn) { btn.disabled = false; btn.textContent = 'Supprimer'; } }
}

let enCoursAjout = false;
async function soumettreNouveauProduit() {
  if (enCoursAjout) return;
  const form = document.getElementById('newProdForm');
  if (!form) return;
  const nom = form.querySelector('[name="nom"]')?.value?.trim();
  if (!nom) { showToast('Veuillez entrer un nom de produit', 'error'); return; }
  enCoursAjout = true;
  const btn = document.querySelector('button[onclick="soumettreNouveauProduit()"]');
  if (btn) { btn.disabled = true; btn.textContent = 'Ajout en cours...'; }
  try {
    const fd = new FormData(form);
    const r = await fetch('/admin/ajouter-produit', { method: 'POST', body: fd });
    const d = await r.json();
    if (d.success) { showToast('Produit ajouté !'); setTimeout(() => location.reload(), 800); }
    else { showToast('Erreur lors de l\'ajout', 'error'); enCoursAjout = false; if (btn) { btn.disabled = false; btn.textContent = 'Ajouter le produit'; } }
  } catch { showToast('Erreur réseau', 'error'); enCoursAjout = false; if (btn) { btn.disabled = false; btn.textContent = 'Ajouter le produit'; } }
}
async function appliquerPromo(id) {
  const pct = document.getElementById('promo_' + id)?.value;
  const r = await fetch('/admin/promotions', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ produit_id: id, reduction: parseFloat(pct) || 0 })
  });
  const d = await r.json();
  if (d.success) showToast('Promotion appliquée !');
}
function togglePrixField() {
  const tp = document.getElementById('typeProduit')?.value;
  const pf = document.getElementById('prixField');
  if (pf) pf.style.display = tp === 'mesure' ? 'none' : 'block';
}
function highlightAdminNav() {
  const path = window.location.pathname;
  document.querySelectorAll('.admin-side-nav a').forEach(a => {
    a.classList.remove('active');
    const href = a.getAttribute('href');
    if (href === path || (path.startsWith(href) && href !== '/admin')) a.classList.add('active');
    else if (href === '/admin' && path === '/admin') a.classList.add('active');
  });
}

// ─── NAVBAR SHADOW ───────────────────────────
window.addEventListener('scroll', () => {
  const nb = document.querySelector('.navbar');
  if (nb) nb.style.boxShadow = window.scrollY > 10 ? '0 2px 20px rgba(44,26,14,0.1)' : '';
});

// ─── INIT ────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  updatePanierBadge();
  checkAdminSession();
  highlightAdminNav();
});
