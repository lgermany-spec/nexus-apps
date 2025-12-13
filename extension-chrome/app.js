const TARIFS = {
  'AUD-001': { libelle: 'Audit réglementaire de paie', tarif: 120, unite: '€/h', cat: 'Audit' },
  'MIS-001': { libelle: 'Mise en place dossier paie', tarif: 120, unite: '€/h', cat: 'Audit' },
  'REP-001': { libelle: 'Reprise de données paie', tarif: 120, unite: '€/h', cat: 'Audit' },
  'BUL-001': { libelle: 'Bulletin (1-20 sal.)', tarif: 20, unite: '€/bul', cat: 'Bulletins' },
  'BUL-004': { libelle: 'Bulletin (+20 sal.)', tarif: 15, unite: '€/bul', cat: 'Bulletins' },
  'ENV-001': { libelle: 'Envoi coffre-fort', tarif: 2, unite: '€/sal', cat: 'Bulletins' },
  'ENV-002': { libelle: 'Envoi papier', tarif: 2, unite: '€/sal', cat: 'Bulletins' },
  'ENT-001': { libelle: 'Entrée salarié', tarif: 15, unite: '€/sal', cat: 'Gestion' },
  'STC-001': { libelle: 'Sortie salarié (STC)', tarif: 50, unite: '€/sal', cat: 'Gestion' },
  'MED-001': { libelle: 'Affiliation médecine travail', tarif: 45, unite: '€/soc', cat: 'Gestion' },
  'MUT-001': { libelle: 'Affiliation mutuelle', tarif: 45, unite: '€/org', cat: 'Gestion' },
  'ATT-001': { libelle: 'Attestation maladie/AT', tarif: 20, unite: '€/att', cat: 'Gestion' },
  'DAT-001': { libelle: 'Déclaration AT', tarif: 30, unite: '€/déc', cat: 'Gestion' },
  'PRV-001': { libelle: 'Dossier prévoyance', tarif: 45, unite: '€/dos', cat: 'Gestion' },
  'SIM-001': { libelle: 'Simulation salaire', tarif: 50, unite: '€/sim', cat: 'Gestion' },
  'BTP-001': { libelle: 'Déclaration CP CI-BTP', tarif: 20, unite: '€/sal', cat: 'BTP' },
  'BTP-002': { libelle: 'Chômage intempéries', tarif: 20, unite: '€/sal', cat: 'BTP' },
  'BTP-003': { libelle: 'Radiation CI-BTP', tarif: 20, unite: '€/sal', cat: 'BTP' },
  'CDI-001': { libelle: 'CDI', tarif: 150, unite: '€/ctr', cat: 'Contrats' },
  'CDD-001': { libelle: 'CDD', tarif: 100, unite: '€/ctr', cat: 'Contrats' },
  'SAI-001': { libelle: 'Contrat saisonnier', tarif: 120, unite: '€/ctr', cat: 'Contrats' },
  'AVE-001': { libelle: 'Avenant (Nexus)', tarif: 70, unite: '€/ave', cat: 'Contrats' },
  'AVE-002': { libelle: 'Avenant (externe)', tarif: 80, unite: '€/ave', cat: 'Contrats' },
  'DUE-001': { libelle: 'DUE Prévoyance', tarif: 200, unite: '€/doc', cat: 'DUE' },
  'DUE-002': { libelle: 'DUE Frais de santé', tarif: 200, unite: '€/doc', cat: 'DUE' },
  'DUE-003': { libelle: 'DUE Retraite sup.', tarif: 200, unite: '€/doc', cat: 'DUE' },
  'DUE-004': { libelle: 'DUE PPV', tarif: 275, unite: '€/doc', cat: 'DUE' },
  'RUP-001': { libelle: 'Rupture conventionnelle', tarif: 350, unite: '€/dos', cat: 'Ruptures' },
  'LIC-001': { libelle: 'Licenciement faute grave', tarif: 200, unite: '€/dos', cat: 'Ruptures' },
  'LIC-002': { libelle: 'Abandon de poste', tarif: 170, unite: '€/dos', cat: 'Ruptures' },
  'LIC-003': { libelle: 'Inaptitude', tarif: 500, unite: '€/dos', cat: 'Ruptures' },
  'LIC-004': { libelle: 'Licenciement éco.', tarif: 750, unite: '€/dos', cat: 'Ruptures' },
  'IND-001': { libelle: 'Indemnité retraite', tarif: 110, unite: '€/calc', cat: 'Indemnités' },
  'IND-002': { libelle: 'Indemnité rup. conv.', tarif: 165, unite: '€/calc', cat: 'Indemnités' },
  'IND-003': { libelle: 'Indemnité inaptitude', tarif: 220, unite: '€/calc', cat: 'Indemnités' },
  'IND-004': { libelle: 'Indemnité lic. éco.', tarif: 330, unite: '€/calc', cat: 'Indemnités' },
  'CON-001': { libelle: 'Conseil RH', tarif: 120, unite: '€/h', cat: 'Autres' },
  'FOR-001': { libelle: 'Dossier OPCO', tarif: 150, unite: '€/dos', cat: 'Autres' },
};

const FORFAIT_CONFIG = { bulletinMoins20: 20, bulletinPlus20: 15, coffreFort: 2, entree: 15, sortie: 50 };

let lignes = [];
let ligneId = 0;

document.addEventListener('DOMContentLoaded', () => { addLigne(); calcForfait(); renderGrille(); });

function switchTab(tab) {
  document.querySelectorAll('.nav-btn').forEach(btn => btn.classList.remove('active'));
  event.target.classList.add('active');
  document.getElementById('tab-devis').classList.toggle('hidden', tab !== 'devis');
  document.getElementById('tab-forfait').classList.toggle('hidden', tab !== 'forfait');
  document.getElementById('tab-grille').classList.toggle('hidden', tab !== 'grille');
}

function addLigne() { ligneId++; lignes.push({ id: ligneId, ref: '', qte: '' }); renderLignes(); }

function removeLigne(id) { if (lignes.length > 1) { lignes = lignes.filter(l => l.id !== id); renderLignes(); calcTotal(); } }

function updateLigne(id, field, value) { const ligne = lignes.find(l => l.id === id); if (ligne) { ligne[field] = value; calcTotal(); } }

function renderLignes() {
  const container = document.getElementById('lignes-container');
  container.innerHTML = lignes.map(l => {
    const tarif = l.ref && TARIFS[l.ref] ? TARIFS[l.ref].tarif : 0;
    const total = l.ref && l.qte ? (tarif * parseFloat(l.qte)).toFixed(2) : '-';
    return `<div class="ligne-row">
      <select onchange="updateLigne(${l.id}, 'ref', this.value)">
        <option value="">Prestation...</option>
        ${Object.entries(TARIFS).map(([ref, t]) => `<option value="${ref}" ${l.ref === ref ? 'selected' : ''}>${t.libelle} (${t.tarif}€)</option>`).join('')}
      </select>
      <input type="number" value="${l.qte}" placeholder="Qté" onchange="updateLigne(${l.id}, 'qte', this.value)" min="0" step="0.5">
      <span class="total">${total !== '-' ? total + '€' : '-'}</span>
      ${lignes.length > 1 ? `<button class="remove-btn" onclick="removeLigne(${l.id})">×</button>` : '<span style="width:28px"></span>'}
    </div>`;
  }).join('');
}

function calcTotal() {
  const total = lignes.reduce((sum, l) => l.ref && l.qte && TARIFS[l.ref] ? sum + (TARIFS[l.ref].tarif * parseFloat(l.qte || 0)) : sum, 0);
  document.getElementById('total-ht').textContent = total.toFixed(2) + ' €';
  document.getElementById('total-net').textContent = total.toFixed(2) + ' €';
}

function calcForfait() {
  const n = parseInt(document.getElementById('forf-sal').value) || 0;
  const entrees = parseInt(document.getElementById('forf-in').value) || 0;
  const sorties = parseInt(document.getElementById('forf-out').value) || 0;
  const coffre = document.getElementById('forf-coffre').checked;
  const prixBul = n <= 20 ? FORFAIT_CONFIG.bulletinMoins20 : FORFAIT_CONFIG.bulletinPlus20;
  const mBul = n * prixBul, mCoffre = coffre ? n * FORFAIT_CONFIG.coffreFort : 0;
  const mIn = entrees * FORFAIT_CONFIG.entree, mOut = sorties * FORFAIT_CONFIG.sortie;
  const total = mBul + mCoffre + mIn + mOut;
  let html = `<div class="result-line"><span>Bulletins (${n} × ${prixBul}€)</span><span class="amount">${mBul.toFixed(2)} €</span></div>`;
  if (coffre) html += `<div class="result-line"><span>Coffre-fort (${n} × 2€)</span><span class="amount">${mCoffre.toFixed(2)} €</span></div>`;
  if (entrees > 0) html += `<div class="result-line"><span>Entrées (${entrees} × 15€)</span><span class="amount">${mIn.toFixed(2)} €</span></div>`;
  if (sorties > 0) html += `<div class="result-line"><span>Sorties (${sorties} × 50€)</span><span class="amount">${mOut.toFixed(2)} €</span></div>`;
  document.getElementById('forfait-details').innerHTML = html;
  document.getElementById('forf-mens').textContent = total.toFixed(2) + ' €';
  document.getElementById('forf-an').textContent = (total * 12).toFixed(2) + ' €';
}

function renderGrille() {
  const cats = {};
  Object.entries(TARIFS).forEach(([ref, t]) => { if (!cats[t.cat]) cats[t.cat] = []; cats[t.cat].push({ ref, ...t }); });
  document.getElementById('grille-content').innerHTML = Object.entries(cats).map(([cat, items]) => `
    <div class="grille-cat"><div class="grille-cat-title">${cat}</div>
    ${items.map(t => `<div class="grille-item"><span><span class="ref">${t.ref}</span>${t.libelle}</span><span class="tarif">${t.tarif} ${t.unite}</span></div>`).join('')}</div>
  `).join('');
}

function openFullVersion() { window.open('https://lgermany-spec.github.io/nexus-apps/calculateur-devis.html', '_blank'); }
