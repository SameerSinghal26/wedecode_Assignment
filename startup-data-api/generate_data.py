import os
import json
import time
import random
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

INDUSTRIES = {
    "FinTech": {
        "focus": "financial technology, payments, banking, investment",
        "products": ["payment platforms", "investment tools", "financial analytics", "crypto solutions"]
    },
    "HealthTech": {
        "focus": "healthcare technology, telemedicine, health monitoring, medical software",
        "products": ["telemedicine platforms", "health trackers", "medical records systems", "AI diagnostics"]
    },
    "EdTech": {
        "focus": "educational technology, online learning, student management, skills training",
        "products": ["learning platforms", "course management", "assessment tools", "skills training"]
    },
    "E-commerce": {
        "focus": "online retail, marketplace, shopping platforms, delivery services",
        "products": ["marketplace platforms", "inventory management", "logistics solutions", "customer analytics"]
    },
    "SaaS": {
        "focus": "software as a service, business tools, productivity, automation",
        "products": ["project management", "CRM systems", "automation tools", "collaboration platforms"]
    },
}

TOTAL_COMPANIES = 10
OUTPUT_FILE = "startup_data.json"
PROGRESS_FILE = "generation_progress.json"

used_company_names = set()
used_product_names = set()

def save_progress(companies: list, current_index: int):
    """Save current progress to file."""
    progress_data = {
        "companies": companies,
        "current_index": current_index,
        "total_target": TOTAL_COMPANIES,
        "used_company_names": list(used_company_names),
        "used_product_names": list(used_product_names),
        "last_updated": time.time()
    }
    
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(progress_data, f, indent=2, ensure_ascii=False)

def load_progress():
    """Load progress from previous run if it exists."""
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                progress_data = json.load(f)
            
            used_company_names.update(progress_data.get("used_company_names", []))
            used_product_names.update(progress_data.get("used_product_names", []))
            
            return progress_data.get("companies", []), progress_data.get("current_index", 0)
        except Exception as e:
            print(f"[WARNING] Could not load progress: {e}")
            return [], 0
    return [], 0

def is_duplicate_company(company_name: str) -> bool:
    """Check if company name is too similar to existing names."""
    name_lower = company_name.lower().strip()
    
    if name_lower in used_company_names:
        return True
    
    name_words = set(name_lower.split())
    for existing in used_company_names:
        existing_words = set(existing.split())
        if name_words and existing_words:
            overlap = len(name_words & existing_words) / max(len(name_words), len(existing_words))
            if overlap >= 0.7:
                return True
    return False

def is_duplicate_product(product_name: str) -> bool:
    """Check if product name already exists."""
    return product_name.lower().strip() in used_product_names

def generate_company_data(industry: str, industry_info: dict) -> dict:
    """Generate a single company with 3-4 products using Claude API."""
    
    num_products = random.choice([3, 4])
    existing_companies = ", ".join(list(used_company_names)[:10]) if used_company_names else "none yet"
    existing_products = ", ".join(list(used_product_names)[:15]) if used_product_names else "none yet"
    
    prompt = f"""Generate realistic data for a {industry} startup company.

INDUSTRY: {industry_info['focus']}
TYPICAL PRODUCTS: {', '.join(industry_info['products'])}

AVOID DUPLICATES:
- Company names: {existing_companies}
- Product names: {existing_products}

Generate EXACTLY {num_products} products.

REALISTIC CONSTRAINTS:
- Founded: 2018-2025
- Employees: 5-120
- Customers: 10-2,000
- Revenue: $500k-$20M
- Growth: 10%-80%
- Target: SMBs, mid-market, clinics, small e-commerce

NO extreme claims or sci-fi features.

Return ONLY this JSON structure:

{{
  "name": "[Unique startup name]",
  "tagline": "[Simple tagline <100 chars]",
  "description": "[2-3 paragraphs, 120-180 words, realistic]",
  "industry": "{industry}",
  "founded_year": [2018-2024],
  "employee_count": [5-120],
  "headquarters": "[City, Country]",
  "website_url": "www.[companyname].com",
  "products": [
    {{
      "name": "[Unique product name]",
      "description": "[2-3 sentences, no hype]",
      "target_audience": "[Realistic buyer: 'SMBs with 20-150 employees']",
      "key_features": "• Feature 1\n• Feature 2\n• Feature 3\n• Feature 4\n• Feature 5",
      "pricing_model": "[Freemium/Subscription/Enterprise]"
    }}
  ]
}}"""

    for attempt in range(5):
        try:
            message = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2500,
                temperature=0.9,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = message.content[0].text.strip()
            
            # Clean markdown formatting
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1])
                if response_text.startswith("json"):
                    response_text = response_text[4:].strip()
            
            company_data = json.loads(response_text)
            
            # Validate structure
            required = ["name", "tagline", "description", "industry", 
                       "founded_year", "employee_count", "headquarters", 
                       "website_url", "products"]
            
            for field in required:
                if field not in company_data:
                    raise ValueError(f"Missing field: {field}")
            
            if len(company_data["products"]) != num_products:
                raise ValueError(f"Expected {num_products} products, got {len(company_data['products'])}")
            
            # Check duplicates
            if is_duplicate_company(company_data["name"]):
                if attempt < 4:
                    continue
                raise ValueError("Duplicate company name")
            
            for product in company_data["products"]:
                if is_duplicate_product(product["name"]):
                    if attempt < 4:
                        continue
                    raise ValueError("Duplicate product name")
            
            # Register names
            used_company_names.add(company_data["name"].lower().strip())
            for product in company_data["products"]:
                used_product_names.add(product["name"].lower().strip())
            
            return company_data
            
        except Exception as e:
            if attempt == 4:
                raise
            time.sleep(2)

def generate_all_data(resume: bool = True):
    """Generate companies with incremental saving and resume capability."""
    
    print("STARTUP DATA GENERATION\n")
    
    existing_companies, start_index = load_progress() if resume else ([], 0)
    
    if existing_companies:
        print(f"Found {len(existing_companies)} companies from previous run")
        if input("Continue? (y/n): ").strip().lower() != 'y':
            for f in [OUTPUT_FILE, PROGRESS_FILE]:
                if os.path.exists(f):
                    os.remove(f)
            existing_companies = []
            start_index = 0
            used_company_names.clear()
            used_product_names.clear()
        print()
    
    print(f"Generating {TOTAL_COMPANIES} companies (3-4 products each)\n")
    
    all_companies = existing_companies
    
    for i in range(start_index, TOTAL_COMPANIES):
        industry = random.choice(list(INDUSTRIES.keys()))
        print(f"[{i + 1}/{TOTAL_COMPANIES}] Generating {industry} company...")
        
        try:
            company = generate_company_data(industry, INDUSTRIES[industry])
            all_companies.append(company)
            
            print(f"   ✓ {company['name']} ({len(company['products'])} products)")
            
            save_progress(all_companies, i + 1)
            time.sleep(1.2)
            
        except Exception as e:
            print(f"   ✗ Failed: {e}\n")
            save_progress(all_companies, i)
            continue
    
    # Final save
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump({"companies": all_companies}, f, indent=2, ensure_ascii=False)
    
    if len(all_companies) == TOTAL_COMPANIES and os.path.exists(PROGRESS_FILE):
        os.remove(PROGRESS_FILE)
    
    total_products = sum(len(c["products"]) for c in all_companies)
    print(f"\n✓ Generated {len(all_companies)} companies, {total_products} products\n")

if __name__ == "__main__":
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("[ERROR] ANTHROPIC_API_KEY not found\n")
        print("Create .env file with: ANTHROPIC_API_KEY=your_key_here\n")
        exit(1)
    
    try:
        generate_all_data(resume=True)
    except KeyboardInterrupt:
        print(f"\n[INTERRUPTED] Progress saved to {PROGRESS_FILE}\n")
    except Exception as e:
        print(f"\n[ERROR] {e}\n")