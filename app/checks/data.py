"""Static reference data used by the deterministic checks.

Kept deliberately small and readable; extend the lists here without touching
any logic.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Brand:
    """A well-known employer that scammers commonly impersonate.

    Attributes:
        name: Display name.
        aliases: Lower-case names as they appear in letter text.
        tokens: Lower-case strings that identify the brand inside a domain label.
        domains: Official registrable domains.
    """

    name: str
    aliases: tuple[str, ...]
    tokens: tuple[str, ...]
    domains: tuple[str, ...]


KNOWN_BRANDS: tuple[Brand, ...] = (
    Brand("TCS", ("tcs", "tata consultancy services"), ("tcs", "tataconsultancy"),
          ("tcs.com", "tata.com")),
    Brand("Infosys", ("infosys",), ("infosys",), ("infosys.com", "infosysbpm.com")),
    Brand("Wipro", ("wipro",), ("wipro",), ("wipro.com",)),
    Brand("HCLTech", ("hcl", "hcltech", "hcl technologies"), ("hcl", "hcltech"), ("hcltech.com", "hcl.com")),
    Brand("Tech Mahindra", ("tech mahindra",), ("techmahindra",), ("techmahindra.com",)),
    Brand("Accenture", ("accenture",), ("accenture",), ("accenture.com",)),
    Brand("Cognizant", ("cognizant",), ("cognizant",), ("cognizant.com",)),
    Brand("Capgemini", ("capgemini",), ("capgemini",), ("capgemini.com",)),
    Brand("Deloitte", ("deloitte",), ("deloitte",), ("deloitte.com",)),
    Brand("IBM", ("ibm",), ("ibm",), ("ibm.com",)),
    Brand("LTIMindtree", ("ltimindtree", "larsen & toubro", "larsen and toubro"),
          ("ltimindtree", "larsentoubro"), ("ltimindtree.com", "larsentoubro.com")),
    Brand("Amazon", ("amazon",), ("amazon",), ("amazon.com", "amazon.in", "amazon.jobs")),
    Brand("Flipkart", ("flipkart",), ("flipkart",), ("flipkart.com", "flipkartcareers.com")),
    Brand("Google", ("google",), ("google",), ("google.com",)),
    Brand("Microsoft", ("microsoft",), ("microsoft",), ("microsoft.com",)),
    Brand("Meta", ("meta platforms", "facebook"), ("meta", "facebook"),
          ("meta.com", "metacareers.com", "facebook.com", "facebookmail.com")),
    Brand("Oracle", ("oracle",), ("oracle",), ("oracle.com",)),
    Brand("Reliance", ("reliance industries", "reliance jio", "jio"), ("reliance", "jio"), ("ril.com", "jio.com")),
    Brand("Airtel", ("airtel", "bharti airtel"), ("airtel",), ("airtel.in", "airtel.com")),
    Brand("HDFC Bank", ("hdfc bank", "hdfc"), ("hdfc", "hdfcbank"), ("hdfcbank.com",)),
    Brand("ICICI Bank", ("icici bank", "icici"), ("icici", "icicibank"), ("icicibank.com",)),
    Brand("Paytm", ("paytm",), ("paytm",), ("paytm.com",)),
    Brand("Zomato", ("zomato",), ("zomato",), ("zomato.com",)),
    Brand("Swiggy", ("swiggy",), ("swiggy",), ("swiggy.com", "swiggy.in")),
    Brand("Amul", ("amul",), ("amul",), ("amul.com", "amul.coop")),
)

FREE_EMAIL_PROVIDERS: frozenset[str] = frozenset({
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.in", "yahoo.in",
    "ymail.com", "rocketmail.com", "outlook.com", "outlook.in", "hotmail.com",
    "live.com", "msn.com", "rediffmail.com", "aol.com", "icloud.com", "me.com",
    "protonmail.com", "proton.me", "gmx.com", "mail.com", "yandex.com",
    "zohomail.in", "zohomail.com", "tutanota.com",
})

# TLDs disproportionately used in phishing (cheap or free to register).
SUSPICIOUS_TLDS: frozenset[str] = frozenset({
    "xyz", "top", "club", "online", "site", "website", "icu", "buzz", "click",
    "link", "live", "shop", "store", "work", "rest", "fit", "gq", "tk", "ml",
    "cf", "ga", "cyou", "sbs", "cfd", "bond", "loan", "win", "vip", "monster",
    "quest",
})

# TLDs accepted when a bare domain (no scheme, no "www.") appears in text.
# Restricting this avoids treating file names like "offer.pdf" as domains.
BARE_DOMAIN_TLDS: frozenset[str] = SUSPICIOUS_TLDS | frozenset({
    "com", "net", "org", "in", "co", "io", "ai", "app", "dev", "me", "info",
    "biz", "us", "uk", "jobs", "careers",
})

URL_SHORTENERS: frozenset[str] = frozenset({
    "bit.ly", "bitly.com", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd",
    "buff.ly", "rebrand.ly", "cutt.ly", "shorturl.at", "rb.gy", "t.ly",
    "tiny.cc", "s.id", "lnkd.in",
})

# Two-level public suffixes common in our target region. Not a full Public
# Suffix List; see README "Limitations".
MULTI_PART_SUFFIXES: frozenset[str] = frozenset({
    "co.in", "net.in", "org.in", "firm.in", "gen.in", "ind.in", "ac.in",
    "edu.in", "gov.in", "res.in", "co.uk", "org.uk", "ac.uk", "gov.uk",
    "com.au", "net.au", "org.au", "co.nz", "com.sg", "com.my", "co.jp",
    "com.br", "co.za", "com.cn",
})

# Words ignored when comparing a company name to a domain.
COMPANY_STOPWORDS: frozenset[str] = frozenset({
    "pvt", "private", "ltd", "limited", "llp", "inc", "corp", "corporation",
    "co", "company", "technologies", "technology", "tech", "solutions",
    "services", "india", "global", "group", "the", "and", "of", "hr",
    "international", "enterprises", "consulting",
})
