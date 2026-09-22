/** Static reference data. Mirrors app/checks/data.py; keep the two in sync. */

export interface Brand {
  name: string;
  aliases: string[];
  tokens: string[];
  domains: string[];
}

const brand = (name: string, aliases: string[], tokens: string[], domains: string[]): Brand => ({
  name,
  aliases,
  tokens,
  domains,
});

export const KNOWN_BRANDS: Brand[] = [
  brand("TCS", ["tcs", "tata consultancy services"], ["tcs", "tataconsultancy"], ["tcs.com", "tata.com"]),
  brand("Infosys", ["infosys"], ["infosys"], ["infosys.com", "infosysbpm.com"]),
  brand("Wipro", ["wipro"], ["wipro"], ["wipro.com"]),
  brand("HCLTech", ["hcl", "hcltech", "hcl technologies"], ["hcl", "hcltech"], ["hcltech.com", "hcl.com"]),
  brand("Tech Mahindra", ["tech mahindra"], ["techmahindra"], ["techmahindra.com"]),
  brand("Accenture", ["accenture"], ["accenture"], ["accenture.com"]),
  brand("Cognizant", ["cognizant"], ["cognizant"], ["cognizant.com"]),
  brand("Capgemini", ["capgemini"], ["capgemini"], ["capgemini.com"]),
  brand("Deloitte", ["deloitte"], ["deloitte"], ["deloitte.com"]),
  brand("IBM", ["ibm"], ["ibm"], ["ibm.com"]),
  brand(
    "LTIMindtree",
    ["ltimindtree", "larsen & toubro", "larsen and toubro"],
    ["ltimindtree", "larsentoubro"],
    ["ltimindtree.com", "larsentoubro.com"],
  ),
  brand("Amazon", ["amazon"], ["amazon"], ["amazon.com", "amazon.in", "amazon.jobs"]),
  brand("Flipkart", ["flipkart"], ["flipkart"], ["flipkart.com", "flipkartcareers.com"]),
  brand("Google", ["google"], ["google"], ["google.com"]),
  brand("Microsoft", ["microsoft"], ["microsoft"], ["microsoft.com"]),
  brand(
    "Meta",
    ["meta platforms", "facebook"],
    ["meta", "facebook"],
    ["meta.com", "metacareers.com", "facebook.com", "facebookmail.com"],
  ),
  brand("Oracle", ["oracle"], ["oracle"], ["oracle.com"]),
  brand("Reliance", ["reliance industries", "reliance jio", "jio"], ["reliance", "jio"], ["ril.com", "jio.com"]),
  brand("Airtel", ["airtel", "bharti airtel"], ["airtel"], ["airtel.in", "airtel.com"]),
  brand("HDFC Bank", ["hdfc bank", "hdfc"], ["hdfc", "hdfcbank"], ["hdfcbank.com"]),
  brand("ICICI Bank", ["icici bank", "icici"], ["icici", "icicibank"], ["icicibank.com"]),
  brand("Paytm", ["paytm"], ["paytm"], ["paytm.com"]),
  brand("Zomato", ["zomato"], ["zomato"], ["zomato.com"]),
  brand("Swiggy", ["swiggy"], ["swiggy"], ["swiggy.com", "swiggy.in"]),
  brand("Amul", ["amul"], ["amul"], ["amul.com", "amul.coop"]),
];

export const FREE_EMAIL_PROVIDERS = new Set([
  "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.in", "yahoo.in",
  "ymail.com", "rocketmail.com", "outlook.com", "outlook.in", "hotmail.com",
  "live.com", "msn.com", "rediffmail.com", "aol.com", "icloud.com", "me.com",
  "protonmail.com", "proton.me", "gmx.com", "mail.com", "yandex.com",
  "zohomail.in", "zohomail.com", "tutanota.com",
]);

export const SUSPICIOUS_TLDS = new Set([
  "xyz", "top", "club", "online", "site", "website", "icu", "buzz", "click",
  "link", "live", "shop", "store", "work", "rest", "fit", "gq", "tk", "ml",
  "cf", "ga", "cyou", "sbs", "cfd", "bond", "loan", "win", "vip", "monster",
  "quest",
]);

export const BARE_DOMAIN_TLDS = new Set([
  ...SUSPICIOUS_TLDS,
  "com", "net", "org", "in", "co", "io", "ai", "app", "dev", "me", "info",
  "biz", "us", "uk", "jobs", "careers",
]);

export const URL_SHORTENERS = new Set([
  "bit.ly", "bitly.com", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd",
  "buff.ly", "rebrand.ly", "cutt.ly", "shorturl.at", "rb.gy", "t.ly",
  "tiny.cc", "s.id", "lnkd.in",
]);

export const MULTI_PART_SUFFIXES = new Set([
  "co.in", "net.in", "org.in", "firm.in", "gen.in", "ind.in", "ac.in",
  "edu.in", "gov.in", "res.in", "co.uk", "org.uk", "ac.uk", "gov.uk",
  "com.au", "net.au", "org.au", "co.nz", "com.sg", "com.my", "co.jp",
  "com.br", "co.za", "com.cn",
]);

export const COMPANY_STOPWORDS = new Set([
  "pvt", "private", "ltd", "limited", "llp", "inc", "corp", "corporation",
  "co", "company", "technologies", "technology", "tech", "solutions",
  "services", "india", "global", "group", "the", "and", "of", "hr",
  "international", "enterprises", "consulting",
]);
