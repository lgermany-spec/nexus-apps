#!/usr/bin/env python3
"""
Agent de mise à jour automatique des données fiscales
pour les simulateurs Nexus Paies Conseils.
"""

import json
import re
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

import requests
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
ROOT_DIR = BASE_DIR.parent
DATA_FILE = BASE_DIR / "data.json"
SIMULATEUR_FILE = ROOT_DIR / "simulateur-fiscal.html"
CALCULATRICE_FILE = ROOT_DIR / "calculatrice-paie.html"
APPRENTI_FILE = ROOT_DIR / "simulateur-apprenti-syntec.html"
RAPPORT_FILE = BASE_DIR / "rapport_maj.md"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "fr-FR,fr;q=0.9",
}


class DataUpdater:
    def __init__(self):
        self.data = self.load_data()
        self.changes = []
        self.errors = []

    def load_data(self) -> Dict[str, Any]:
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Fichier non trouvé : {DATA_FILE}")
            return {}

    def save_data(self):
        self.data['meta']['last_update'] = datetime.now().strftime('%Y-%m-%d')
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
        logger.info("Données sauvegardées")

    def fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        try:
            response = requests.get(url, headers=HEADERS, timeout=30)
            response.raise_for_status()
            return BeautifulSoup(response.text, 'html.parser')
        except requests.RequestException as e:
            logger.error(f"Erreur HTTP {url}: {e}")
            self.errors.append(f"Erreur HTTP: {e}")
            return None

    def clean_number(self, text: str) -> str:
        return text.replace(' ', '').replace('\u202f', '').replace('\u00a0', '').replace('\xa0', '')

    def update_cotisations_urssaf(self) -> bool:
        logger.info("Vérification cotisations URSSAF...")
        urls = [
            "https://www.autoentrepreneur.urssaf.fr/portail/accueil/sinformer-sur-le-statut/lessentiel-du-statut.html",
            "https://entreprendre.service-public.fr/vosdroits/F23267",
        ]
        for url in urls:
            soup = self.fetch_page(url)
            if not soup:
                continue
            text = soup.get_text()
            bnc_patterns = [
                r'(?:BNC|libéral|libérales).*?(\d{1,2}[,\.]\d{1,2})\s*%',
                r'(\d{1,2}[,\.]\d{1,2})\s*%.*?(?:BNC|libéral)',
            ]
            for pattern in bnc_patterns:
                match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
                if match:
                    new_rate = float(match.group(1).replace(',', '.')) / 100
                    old_rate = self.data['cotisations_sociales']['bnc']['normal']
                    if not (0.20 <= new_rate <= 0.30):
                        logger.warning(f"Taux BNC suspect ignoré : {new_rate*100:.1f}%")
                        continue
                    if abs(new_rate - old_rate) > 0.001:
                        self.changes.append({
                            'type': 'cotisation',
                            'champ': 'BNC',
                            'ancien': f"{old_rate*100:.1f}%",
                            'nouveau': f"{new_rate*100:.1f}%",
                            'source': url
                        })
                        self.data['cotisations_sociales']['bnc']['normal'] = new_rate
                        self.data['cotisations_sociales']['bnc']['acre'] = new_rate / 2
                    break
            return True
        self.errors.append("Impossible de récupérer les taux URSSAF")
        return False

    def update_pmss_smic(self) -> bool:
        logger.info("Vérification PMSS et SMIC...")
        url = "https://www.service-public.fr/particuliers/vosdroits/F2300"
        soup = self.fetch_page(url)
        if not soup:
            return False
        
        text = soup.get_text()
        annee = datetime.now().year
        
        # Recherche SMIC horaire
        smic_pattern = r'(\d{1,2}[,\.]\d{2})\s*(?:€|euros?).*?(?:brut|heure|horaire)'
        match = re.search(smic_pattern, text, re.IGNORECASE)
        if match:
            smic_h = float(match.group(1).replace(',', '.'))
            if 10 <= smic_h <= 15:
                old_smic = self.data.get('smic_horaire', {}).get(str(annee), 0)
                if abs(smic_h - old_smic) > 0.01:
                    self.changes.append({
                        'type': 'smic',
                        'champ': f'SMIC horaire {annee}',
                        'ancien': f"{old_smic} €",
                        'nouveau': f"{smic_h} €",
                        'source': url
                    })
                    if 'smic_horaire' not in self.data:
                        self.data['smic_horaire'] = {}
                    if 'smic_mensuel' not in self.data:
                        self.data['smic_mensuel'] = {}
                    self.data['smic_horaire'][str(annee)] = smic_h
                    self.data['smic_mensuel'][str(annee)] = round(smic_h * 151.67, 2)
        
        # Recherche PMSS
        url2 = "https://www.urssaf.fr/accueil/outils-documentation/taux-baremes/plafonds.html"
        soup2 = self.fetch_page(url2)
        if soup2:
            text2 = soup2.get_text()
            pmss_pattern = r'(\d[\d\s]*)\s*(?:€|euros?).*?(?:mensuel|PMSS|plafond)'
            match = re.search(pmss_pattern, text2, re.IGNORECASE)
            if match:
                pmss = int(self.clean_number(match.group(1)))
                if 3500 <= pmss <= 5000:
                    old_pmss = self.data.get('pmss', {}).get(str(annee), 0)
                    if pmss != old_pmss:
                        self.changes.append({
                            'type': 'pmss',
                            'champ': f'PMSS {annee}',
                            'ancien': f"{old_pmss} €",
                            'nouveau': f"{pmss} €",
                            'source': url2
                        })
                        if 'pmss' not in self.data:
                            self.data['pmss'] = {}
                        self.data['pmss'][str(annee)] = pmss
        
        return True

    def update_bareme_ir(self) -> bool:
        logger.info("Vérification barème IR...")
        url = "https://www.service-public.fr/particuliers/vosdroits/F1419"
        soup = self.fetch_page(url)
        if not soup:
            return False
        text = soup.get_text()
        tranches_pattern = r"(?:jusqu[''']à|de\s+\d[\d\s]*(?:€|euros?)?\s+à)\s*(\d[\d\s]*)\s*(?:€|euros?).*?(\d{1,2})\s*%"
        matches = re.findall(tranches_pattern, text, re.IGNORECASE)
        if matches:
            logger.info(f"Tranches IR trouvées : {len(matches)}")
            premiere_tranche = int(self.clean_number(matches[0][0]))
            old_premiere = self.data['bareme_ir']['tranches'][0]['plafond']
            if premiere_tranche != old_premiere:
                self.changes.append({
                    'type': 'ir',
                    'champ': '1ère tranche IR',
                    'ancien': f"{old_premiere:,} €".replace(',', ' '),
                    'nouveau': f"{premiere_tranche:,} €".replace(',', ' '),
                    'source': url
                })
                self.data['bareme_ir']['tranches'][0]['plafond'] = premiere_tranche
            return True
        return False

    def update_plafonds_micro(self) -> bool:
        logger.info("Vérification plafonds micro...")
        url = "https://entreprendre.service-public.fr/vosdroits/F32353"
        soup = self.fetch_page(url)
        if not soup:
            return False
        text = soup.get_text()
        vente_pattern = r'(\d{3}\s*\d{3})\s*(?:€|euros?).*?(?:vente|marchandises|commerc)'
        match = re.search(vente_pattern, text, re.IGNORECASE)
        if match:
            plafond = int(self.clean_number(match.group(1)))
            old_plafond = self.data['plafonds_micro']['vente_marchandises']
            if (180000 <= plafond <= 200000) and plafond != old_plafond:
                self.changes.append({
                    'type': 'plafond',
                    'champ': 'Plafond vente',
                    'ancien': f"{old_plafond:,} €".replace(',', ' '),
                    'nouveau': f"{plafond:,} €".replace(',', ' '),
                    'source': url
                })
                self.data['plafonds_micro']['vente_marchandises'] = plafond
        services_pattern = r'(?:services?|prestations?).*?(\d{2}\s*\d{3})\s*(?:€|euros?)'
        match = re.search(services_pattern, text, re.IGNORECASE)
        if match:
            plafond = int(self.clean_number(match.group(1)))
            old_plafond = self.data['plafonds_micro']['prestations_services']
            if (75000 <= plafond <= 85000) and plafond != old_plafond:
                self.changes.append({
                    'type': 'plafond',
                    'champ': 'Plafond services',
                    'ancien': f"{old_plafond:,} €".replace(',', ' '),
                    'nouveau': f"{plafond:,} €".replace(',', ' '),
                    'source': url
                })
                self.data['plafonds_micro']['prestations_services'] = plafond
        return True

    def update_simulateur_html(self):
        if not SIMULATEUR_FILE.exists():
            logger.warning(f"Simulateur fiscal non trouvé")
            return False
        logger.info("Mise à jour simulateur fiscal...")
        with open(SIMULATEUR_FILE, 'r', encoding='utf-8') as f:
            html = f.read()
        cotis = self.data['cotisations_sociales']
        replacements = [
            (r"'bnc':\s*\{\s*normal:\s*[\d.]+,\s*acre:\s*[\d.]+",
             f"'bnc': {{ normal: {cotis['bnc']['normal']}, acre: {cotis['bnc']['acre']}"),
            (r"'bic-services':\s*\{\s*normal:\s*[\d.]+,\s*acre:\s*[\d.]+",
             f"'bic-services': {{ normal: {cotis['bic_services']['normal']}, acre: {cotis['bic_services']['acre']}"),
            (r"'bic-vente':\s*\{\s*normal:\s*[\d.]+,\s*acre:\s*[\d.]+",
             f"'bic-vente': {{ normal: {cotis['bic_vente']['normal']}, acre: {cotis['bic_vente']['acre']}"),
        ]
        for pattern, replacement in replacements:
            html = re.sub(pattern, replacement, html)
        with open(SIMULATEUR_FILE, 'w', encoding='utf-8') as f:
            f.write(html)
        logger.info("Simulateur fiscal OK")
        return True

    def update_calculatrice_html(self):
        if not CALCULATRICE_FILE.exists():
            logger.warning(f"Calculatrice paie non trouvée")
            return False
        logger.info("Mise à jour calculatrice paie...")
        with open(CALCULATRICE_FILE, 'r', encoding='utf-8') as f:
            html = f.read()
        
        # MAJ PMSS
        if 'pmss' in self.data:
            for annee, valeur in self.data['pmss'].items():
                html = re.sub(rf'({annee}:\s*)\d+', rf'\g<1>{valeur}', html)
        
        # MAJ SMIC
        if 'smic_horaire' in self.data:
            for annee, valeur in self.data['smic_horaire'].items():
                pattern = rf'(SMIC_HORAIRE\s*=\s*\{{[^}}]*{annee}:\s*)[\d.]+'
                html = re.sub(pattern, rf'\g<1>{valeur}', html)
        
        if 'smic_mensuel' in self.data:
            for annee, valeur in self.data['smic_mensuel'].items():
                pattern = rf'(SMIC_MENSUEL\s*=\s*\{{[^}}]*{annee}:\s*)[\d.]+'
                html = re.sub(pattern, rf'\g<1>{valeur}', html)
        
        with open(CALCULATRICE_FILE, 'w', encoding='utf-8') as f:
            f.write(html)
        logger.info("Calculatrice paie OK")
        return True

    def update_apprenti_html(self):
        if not APPRENTI_FILE.exists():
            logger.warning(f"Simulateur apprenti non trouvé")
            return False
        logger.info("Mise à jour simulateur apprenti Syntec...")
        with open(APPRENTI_FILE, 'r', encoding='utf-8') as f:
            html = f.read()
        
        # MAJ SMIC dans CONSTANTES
        if 'smic_mensuel' in self.data:
            for annee, valeur in self.data['smic_mensuel'].items():
                # Pattern: SMIC: 1801.80 ou SMIC: 1823.03
                pattern = rf'({annee}:\s*\{{\s*SMIC:\s*)[\d.]+'
                html = re.sub(pattern, rf'\g<1>{valeur}', html)
        
        if 'smic_horaire' in self.data:
            for annee, valeur in self.data['smic_horaire'].items():
                pattern = rf'(SMIC_HORAIRE:\s*)[\d.]+(\s*,?\s*//.*?{annee}|[^}}]*{annee})'
                # Plus simple: chercher SMIC_HORAIRE: XX.XX dans le bloc de l'année
                pattern = rf'({annee}:\s*\{{[^}}]*SMIC_HORAIRE:\s*)[\d.]+'
                html = re.sub(pattern, rf'\g<1>{valeur}', html)
        
        with open(APPRENTI_FILE, 'w', encoding='utf-8') as f:
            f.write(html)
        logger.info("Simulateur apprenti OK")
        return True

    def generate_report(self) -> str:
        report = f"""# Rapport - {datetime.now().strftime('%d/%m/%Y %H:%M')}

## Résumé
- **Changements** : {len(self.changes)}
- **Erreurs** : {len(self.errors)}

## Fichiers mis à jour
- simulateur-fiscal.html
- calculatrice-paie.html
- simulateur-apprenti-syntec.html

"""
        if self.changes:
            report += "## Modifications\n\n| Type | Champ | Ancien | Nouveau |\n|------|-------|--------|--------|\n"
            for c in self.changes:
                report += f"| {c['type']} | {c['champ']} | {c['ancien']} | {c['nouveau']} |\n"
        else:
            report += "## Aucune modification\nLes données sont à jour.\n"
        if self.errors:
            report += "\n## Erreurs\n"
            for e in self.errors:
                report += f"- {e}\n"
        return report

    def run(self, update_html: bool = True) -> bool:
        logger.info("=" * 50)
        logger.info("Démarrage mise à jour")
        logger.info("=" * 50)
        self.update_cotisations_urssaf()
        self.update_pmss_smic()
        self.update_bareme_ir()
        self.update_plafonds_micro()
        self.save_data()
        if update_html:
            self.update_simulateur_html()
            self.update_calculatrice_html()
            self.update_apprenti_html()
        report = self.generate_report()
        with open(RAPPORT_FILE, 'w', encoding='utf-8') as f:
            f.write(report)
        print("\n" + "=" * 50)
        if self.changes:
            print(f"✅ {len(self.changes)} modification(s)")
        else:
            print("✅ Données à jour")
        print("=" * 50)
        return len(self.errors) == 0


def main():
    updater = DataUpdater()
    return 0 if updater.run() else 1


if __name__ == "__main__":
    exit(main())
