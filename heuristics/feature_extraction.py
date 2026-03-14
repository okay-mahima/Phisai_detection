import re
import numpy as np
from urllib.parse import urlparse

# Global lists updated for better coverage
brands = ["google", "microsoft", "apple", "paypal", "amazon", "netflix", "facebook", "instagram", "spotify", "binance", "metamask", "coinbase"]
susp_tlds = [".tk", ".ml", ".ga", ".cf", ".gq", ".xyz", ".top", ".pw", ".bid", ".loan", ".net", ".org"] 
shorteners = ["bit.ly", "goo.gl", "t.co", "tinyurl.com", "is.gd"]

# Behavioral Categories
urgency_words = ['urgent', 'immediately', 'now', 'within 24 hours', 'act now', 'action required', 'detected', 'unusual activity']
fear_words = ['suspended', 'blocked', 'unauthorized', 'compromised', 'alert', 'security issue', 'safeguard', 'funds at risk']
authority_words = ['official', 'support', 'admin', 'department', 'team', 'security team', 'hr department']
reward_words = ['winner', 'congratulations', 'selected', 'salary', 'bonus', 'claim', 'exclusive']
polite_words = ['kindly', 'please', 'appreciate', 'cooperation', 'sincerely', 'best regards', 'valued user']

def extract_urls(text):
    return re.findall(r'https?://[^\s<>"\'()]+', str(text))

def url_features(urls, original_text=""):
    feats = []
    text_lower = original_text.lower()
    
    for url in urls[:3]:
        t = url.lower()
        try:
            p = urlparse(url)
            d = p.netloc.lower()
            pq = (p.path + '?' + p.query).lower()

            # 1. 🔥 BRAND-DOMAIN MISMATCH (Job Scam Fix)
            is_fake_brand_domain = 0
            for b in brands:
                if b in text_lower and b in d:
                    # Agar brand text mein hai aur domain mein bhi, par official TLD nahi hai
                    if not (d.endswith(f"{b}.com") or d.endswith(f"{b}.co.in")):
                        is_fake_brand_domain = 1
            
            # 2. 🔥 GENERIC SECURITY DOMAIN (Crypto Scam Fix)
            # Detects domains like 'wallet-protection-service.net'
            is_generic_scam_domain = int(any(w in d for w in ['wallet', 'protection', 'secure', 'verify', 'crypto', 'login-']))

            feats += [
                int(len(t) > 70),
                int(d.count('.') > 2),
                int('-' in d),
                int('@' in t),
                int(any(b in d for b in brands)), 
                int(any(tld in d for tld in susp_tlds)),
                int(any(s in t for s in shorteners)),
                int('https' in t),
                int(is_fake_brand_domain),      # Feature 9
                int(is_generic_scam_domain),    # Feature 10 (NEW)
                int(pq.count('?') > 1),
                int(bool(re.search(r'\d{6,}', t))),
                int(any(w in t for w in ['secure', 'check', 'onboarding', 'verify'])),
                int(t.count('/') > 5),
                int(len(d) > 22),
                int(sum(c.isdigit() for c in d) / len(d) > 0.15 if d else 0),
                int(d.startswith('www-') or d.startswith('secure-')),
                int('.html' in pq or '.php' in pq)
            ]
        except:
            feats += [0] * 18
    return feats + [0] * (54 - len(feats))

def webpage_features(text):
    t = str(text).lower()
    feats = [
        int('<form' in t or 'action=' in t),
        int('type="password"' in t),
        int('type="hidden"' in t),
        int('<iframe' in t),
        int('window.location' in t),
        int('<script' in t),
        int('src=' in t and '.js' in t),
        int('eval(' in t),
        int('window.open' in t),
        int(len(t) > 1200),
        int('login' in t and 'form' in t),
        int('trust' in t or 'secure' in t),
        int(t.count('href="#"') > 2),
        int('autocomplete="off"' in t),
        int('onboarding' in t or 'background check' in t), 
        int(t.count('<img') < 2)
    ]
    return feats + [0] * (25 - len(feats))

def email_features(text):
    t = str(text).lower()
    # Spotify/Renew logic (Safety override)
    is_info = int(any(p in t for p in ["no action needed", "receipt", "thanks for listening"]))
    
    feats = [
        int(any(x in t for x in ['@gmail', '@yahoo', '@hotmail'])),
        int('attachment' in t),
        int(('href=' in t or 'https' in t) and not is_info), 
        int(any(w in t for w in ['password', 'credentials', 'wallet', 'seed phrase'])),
        int(len(t) < 100 or len(t) > 5000),
        int(any(w in t for w in urgency_words) and not is_info),
        int("valued user" in t or "dear applicant" in t)
    ]

    feats += [
        int(len(re.findall(r'\b[A-Z]{5,}\b', t)) > 4), 
        int(t.count('!') > 2),
        int("please" in t and ("verify" in t or "check" in t) and not is_info),
        int("best regards" in t or "security team" in t),
        int("salary" in t or "payment" in t), 
        int("account" in t and ("update" in t or "risk" in t)),
        int(any(w in t for w in polite_words) and any(w in t for w in urgency_words)), 
        int(t.count('http') > 1),
        int(len(set(t.split())) / len(t.split()) < 0.6 if t.split() else 0)
    ]
    return feats + [0] * (30 - len(feats))

def psych_features(text):
    t = str(text).lower()
    
    feats = [
        sum(w in t for w in urgency_words),
        sum(w in t for w in fear_words),
        sum(w in t for w in authority_words),
        sum(w in t for w in reward_words), 
        int(any(w in t for w in ['limited', '24 hours', 'immediately'])),
        int('click here' in t and (sum(w in t for w in fear_words) > 0)), 
        int('official' in t or 'partner' in t),
        int(any(w in t for w in polite_words)),
        int("dear applicant" in t or "selected" in t), 
        int(t.count('!') > 2),
        int("please" in t and "verify" in t),
        int("unusual activity" in t or "detected" in t),
        int("wallet" in t or "crypto" in t),
        int('verified by' in t or 'secure' in t)
    ]
    return feats + [0] * (25 - len(feats))

def extract_all_features(text):
    urls = extract_urls(text)
    f_url = url_features(urls, text) 
    f_web = webpage_features(text)
    f_email = email_features(text)
    f_psych = psych_features(text)

    all_features = np.concatenate([f_url, f_web, f_email, f_psych])
    return all_features.astype(float)