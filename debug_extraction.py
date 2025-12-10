from urllib.parse import urlparse
import pandas as pd
import re

def extract_domain(url_list_str):
    """Extract domains from a comma-separated string of URLs."""
    if not url_list_str or pd.isna(url_list_str):
        print(f"Skipping empty/NaN input: {url_list_str}")
        return []
    
    print(f"Processing: '{url_list_str}' (Type: {type(url_list_str)})")
    
    domains = []
    # URLs in TSV might be separated by comma or space
    urls = re.findall(r'(https?://\S+)', str(url_list_str))
    print(f"  Found URLs: {urls}")
    
    for url in urls:
        try:
            domain = urlparse(url).netloc.replace('www.', '')
            if domain:
                domains.append(domain)
        except Exception as e:
            print(f"  Error parsing {url}: {e}")
            pass
    return domains

print("--- Test 1: Simple ---")
res = extract_domain("https://reuters.com/article1, https://cnn.com")
print(f"Result: {res}")

print("\n--- Test 2: Real Data Sample (from Tesla Debug) ---")
# Copied from previous debug output step 391
sample_text = "https://help.twitter.com/en/rules-and-policies/financial-scam    https://consumer.ftc.gov/articles/what-know-about-cryptocurrency-and-scams#scams"
res2 = extract_domain(sample_text)
print(f"Result: {res2}")

print("\n--- Test 3: Null/None ---")
res3 = extract_domain(None)
print(f"Result: {res3}")
