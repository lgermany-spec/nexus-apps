#!/usr/bin/env python3
"""
Agent de mise à jour automatique des données fiscales
pour le simulateur Nexus Paies Conseils.
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
            logger.warning(f"Simulateur non trouvé : {SIMULATEUR_FILE}")
            return False
        logger.info("Mise à jour simulateur HTML...")
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
        tranches = self.data['bareme_ir']['tranches']
        ir_pattern = r"const TRANCHES_IR_\d{4}\s*=\s*\[[\s\S]*?\];"
        new_tranches = "const TRANCHES_IR_2025 = [\n"
        for t in tranches:
            plafond = t['plafond'] if t['plafond'] else 'Infinity'
            new_tranches += f"            {{ plafond: {plafond}, taux: {t['taux']} }},\n"
        new_tranches += "        ];"
        html = re.sub(ir_pattern, new_tranches, html)
        with open(SIMULATEUR_FILE, 'w', encoding='utf-8') as f:
            f.write(html)
        logger.info("Simulateur mis à jour")
        return True

    def generate_report(self) -> str:
        report = f"""# Rapport - {datetime.now().strftime('%d/%m/%Y %H:%M')}

## Résumé
- **Changements** : {len(self.changes)}
- **Erreurs** : {len(self.errors)}

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
        self.update_bareme_ir()
        self.update_plafonds_micro()
        self.save_data()
        if update_html and self.changes:
            self.update_simulateur_html()
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
