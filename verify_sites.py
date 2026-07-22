"""
verify_sites.py - Verifica independentemente os 10 sites e gera dados
para o relatorio comparativo com o Vigilantia.
Usa apenas requests + BeautifulSoup (sem Playwright).
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0 Safari/537.36"
    ),
    "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
}

SITES = [
    "https://www.pcm.pt",
    "https://www.citeforma.pt",
    "https://www.wikipedia.pt",
    "https://www.sapo.pt",
    "https://www.publico.pt",
    "https://www.jn.pt",
    "https://www.expresso.pt",
    "https://www.youtube.pt",
    "https://www.google.pt",
    "https://www.cloudflare.com",
]

def check_site(url):
    r = {"url": url, "error": None}
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        r["status"] = resp.status_code
        r["final_url"] = resp.url
        r["reachable"] = resp.ok
        if not resp.ok:
            r["error"] = f"HTTP {resp.status_code}"
            return r
        html = resp.text
        soup = BeautifulSoup(html, "html.parser")
        base_domain = urlparse(url).hostname or ""

        # Privacy policy link
        privacy_kw = ["privacy", "privacidade", "politica de privacidade",
                       "cookies", "terms", "termos", "protecion de datos"]
        r["privacy_link"] = None
        for a in soup.find_all("a"):
            text = (a.get_text() or "").strip().lower()
            href = a.get("href", "")
            if any(kw in text for kw in privacy_kw) and href:
                r["privacy_link"] = urljoin(url, href)
                break

        # Cookie banner text
        banner_kw = ["aceitar cookies", "accept cookies", "cookie consent",
                      "este site utiliza cookies", "we use cookies",
                      "utilizamos cookies", "usamos cookies",
                      "this website uses cookies", "cookie policy",
                      "aceitar todos", "accept all"]
        page_text = soup.get_text().lower()
        r["has_cookie_banner_text"] = any(kw in page_text for kw in banner_kw)

        # Cookie banner via class/id heuristic
        consent_ids = ["cookie", "consent", "gdpr", "cookieadmin", "onetrust",
                       "didomi", "quantcast", "consentimento"]
        r["has_cookie_banner_element"] = False
        for el in soup.find_all(["div", "section", "aside"]):
            el_id = (el.get("id") or "").lower()
            el_class = " ".join(el.get("class") or []).lower()
            if any(cid in el_id or cid in el_class for cid in consent_ids):
                r["has_cookie_banner_element"] = True
                break
        # Also check scripts for CMP
        for script in soup.find_all("script"):
            src = (script.get("src") or "").lower()
            txt = (script.string or "").lower()
            if any(x in src or x in txt for x in ["cookieadmin", "onetrust",
                "didomi", "quantcast", "cookie-consent", "cookieconsent",
                "consent", "cookiebot"]):
                r["has_cookie_banner_element"] = True
                break

        # Google Analytics
        r["has_google_analytics"] = False
        for script in soup.find_all("script"):
            src = (script.get("src") or "")
            txt = (script.string or "")
            if "google-analytics" in src or "gtag/js" in src:
                r["has_google_analytics"] = True
            if "google-analytics" in txt or "gtag" in txt or "GA_MEASUREMENT_ID" in txt:
                r["has_google_analytics"] = True

        # Third party scripts
        tp_scripts = []
        for script in soup.find_all("script"):
            src = script.get("src", "")
            if src:
                sd = urlparse(src).hostname or ""
                if sd and sd != base_domain and not sd.endswith(f".{base_domain}"):
                    tp_scripts.append(src)
        r["third_party_scripts"] = tp_scripts[:10]
        r["third_party_scripts_count"] = len(tp_scripts)

        # Forms with personal data
        personal = ["email", "e-mail", "phone", "telefone", "nome",
                     "name", "address", "morada", "password", "senha"]
        forms_with_data = []
        for form in soup.find_all("form"):
            fields = []
            for inp in form.find_all(["input", "textarea"]):
                name = (inp.get("name") or "").lower()
                typ = (inp.get("type") or "").lower()
                placeholder = (inp.get("placeholder") or "").lower()
                if any(p in name or p in typ or p in placeholder for p in personal):
                    fields.append(name or typ or placeholder)
            if fields:
                # Check nearby privacy notice
                form_text = form.get_text().lower()
                notice_kw = ["dados pessoais", "privacidade", "rgpd", "gdpr",
                             "finalidade", "privacy"]
                has_notice = any(nk in form_text for nk in notice_kw)
                parent = form.parent
                if parent:
                    parent_text = parent.get_text().lower()
                    has_notice = has_notice or any(nk in parent_text for nk in notice_kw)
                forms_with_data.append({
                    "fields": fields,
                    "has_privacy_notice": has_notice
                })
        r["forms_with_personal_data"] = forms_with_data

    except Exception as exc:
        r["error"] = str(exc)
        r["reachable"] = False

    return r


# Check privacy policy content
def check_privacy_policy(url):
    if not url:
        return None
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        if not resp.ok:
            return {"error": f"HTTP {resp.status_code}", "url": url}
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style"]):
            tag.decompose()
        text = soup.get_text(separator=" ").lower()

        flags = {}
        # DPO
        dpo_kw = ["encarregado de protecao de dados", "encarregado de proteccion de dados",
                   "data protection officer", "dpo", "contacto do dpo",
                   "encarregado de protecion"]
        flags["dpo_contact"] = any(kw in text for kw in dpo_kw)

        # Right of access
        access_kw = ["direito de acesso", "acesso aos dados", "right of access",
                     "access to your data", "aceder aos seus dados"]
        flags["right_access"] = any(kw in text for kw in access_kw)

        # Right to erasure
        erasure_kw = ["direito ao apagamento", "direito a ser esquecido",
                      "apagar os seus dados", "right to erasure",
                      "right to be forgotten", "delete your data",
                      "eliminar os seus dados"]
        flags["right_erasure"] = any(kw in text for kw in erasure_kw)

        # International transfers
        transfer_kw = ["transferencia internacional", "fora da uniao europeia",
                       "outside the eu", "united states", "estados unidos",
                       "eua", "pais terceiro", "standard contractual clauses",
                       "clausulas contratuais", "international transfers",
                       "outside the eea", "fora do espaco economico europeu"]
        flags["international_transfers"] = any(kw in text for kw in transfer_kw)

        # Retention period
        retention_kw = ["prazo de conservacao", "periodo de conservacao",
                        "retention period", "how long we keep",
                        "tempo de conservacao", "prazo de retencao",
                        "periodo de retencao", "storage period",
                        "durante quanto tempo"]
        flags["retention_period"] = any(kw in text for kw in retention_kw)

        return {"url": url, "flags": flags}
    except Exception as exc:
        return {"error": str(exc), "url": url}


def main():
    results = []
    for url in SITES:
        print(f"A verificar: {url} ... ", end="", flush=True)
        r = check_site(url)

        # Also check privacy policy
        pp = check_privacy_policy(r.get("privacy_link"))
        r["privacy_policy_check"] = pp
        results.append(r)
        print(f"OK" if r.get("reachable") else f"FALHOU ({r.get('error')})")

    out = os.path.join(os.path.dirname(__file__), "site_verification_results.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nResultados guardados em: {out}")


if __name__ == "__main__":
    main()
