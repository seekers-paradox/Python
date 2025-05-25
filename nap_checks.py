import pandas as pd
import googlemaps
import time
import re
from difflib import SequenceMatcher

# === CONFIGURATION ===
API_KEY = 'API key Google Places API'  # Replace this securely
INPUT_CSV = 'MT15_data_export.csv'
OUTPUT_CSV = 'nap_audit_results_cleaned.csv'

# === HELPER FUNCTIONS ===
def normalize_phone(phone):
    """Extract and normalize phone numbers to digits only"""
    if not phone or pd.isna(phone):
        return ""
    # Remove all non-digit characters
    digits_only = re.sub(r'\D', '', str(phone))
    # Handle US numbers - keep last 10 digits if longer
    if len(digits_only) > 10:
        digits_only = digits_only[-10:]
    return digits_only

def similarity_ratio(a, b):
    """Calculate similarity ratio between two strings"""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()

def normalize_text_for_comparison(text):
    """Normalize text for comparison - remove extra spaces, punctuation"""
    if not text or pd.isna(text):
        return ""
    # Convert to lowercase, remove extra spaces and common punctuation
    normalized = re.sub(r'[^\w\s]', ' ', str(text).lower())
    normalized = ' '.join(normalized.split())  # Remove extra whitespace
    return normalized

def format_full_address(row):
    """Format complete address including city, zip, and country"""
    components = []
    
    # Add address
    address = str(row.get("Address", "")).strip()
    if address and address != "nan":
        components.append(address)
    
    # Add city
    city = str(row.get("City", "")).strip()
    if city and city != "nan":
        components.append(city)
    
    # Add zip code if available
    zip_code = str(row.get("ZipCode", "")).strip()
    if zip_code and zip_code != "nan":
        components.append(zip_code)
    
    # Add country (default to USA if not specified)
    country = str(row.get("Country", "USA")).strip()
    if country and country != "nan":
        components.append(country)
    
    return ", ".join(components)

def check_name_match(input_name, api_name, threshold=0.80):
    """Check if business names match with flexible logic"""
    if not input_name or not api_name:
        return False, 0.0
    
    # Normalize both names
    norm_input = normalize_text_for_comparison(input_name)
    norm_api = normalize_text_for_comparison(api_name)
    
    # Calculate similarity
    similarity = similarity_ratio(norm_input, norm_api)
    
    # Also check if one name contains the other (for cases like "ABC Corp" vs "ABC Corporation")
    contains_match = (norm_input in norm_api) or (norm_api in norm_input)
    
    return (similarity >= threshold) or contains_match, similarity

def check_address_match(input_address, api_address, threshold=0.85):
    """Check if addresses match with flexible logic"""
    if not input_address or not api_address:
        return False, 0.0
    
    # Normalize addresses
    norm_input = normalize_text_for_comparison(input_address)
    norm_api = normalize_text_for_comparison(api_address)
    
    # Calculate similarity
    similarity = similarity_ratio(norm_input, norm_api)
    
    # Check if key components are present
    input_parts = norm_input.split()
    api_parts = norm_api.split()
    
    # Check if most significant parts match
    key_matches = 0
    total_parts = len(input_parts)
    
    for part in input_parts:
        if len(part) > 2 and any(part in api_part for api_part in api_parts):
            key_matches += 1
    
    component_match_ratio = key_matches / max(total_parts, 1) if total_parts > 0 else 0
    
    return (similarity >= threshold) or (component_match_ratio >= 0.7), max(similarity, component_match_ratio)

def check_phone_match(input_phone, api_phone):
    """Check if phone numbers match"""
    norm_input = normalize_phone(input_phone)
    norm_api = normalize_phone(api_phone)
    
    if not norm_input or not norm_api:
        return False, 0.0
    
    # Exact match
    if norm_input == norm_api:
        return True, 1.0
    
    # Check if one contains the other (for cases with extensions)
    if norm_input in norm_api or norm_api in norm_input:
        return True, 0.9
    
    return False, 0.0

# === INIT ===
gmaps = googlemaps.Client(key=API_KEY)
df = pd.read_csv(INPUT_CSV)

# Clean and normalize headers
df.columns = [col.strip() for col in df.columns]
results = []

print(f"📊 Processing {len(df)} records...")

# === MAIN LOOP ===
for index, row in df.iterrows():
    business_name = str(row.get("CompanyName", "")).strip()
    phone = str(row.get("WorkNumber", "")).strip()
    full_address = format_full_address(row)

    # Create search query
    query = f"{business_name} {full_address}"

    print(f"🔍 [{index+1}/{len(df)}] Searching for: {business_name}")
    
    try:
        places_result = gmaps.places(query=query)
        time.sleep(1)  # Rate limit buffer

        if not places_result['results']:
            results.append({
                "Input Business Name": business_name,
                "Input Phone": phone,
                "Input Address": full_address,
                "API Name": "",
                "API Phone": "",
                "API Address": "",
                "Name Match": "No",
                "Address Match": "No", 
                "Phone Match": "No",
                "Name Similarity": 0.0,
                "Address Similarity": 0.0,
                "Phone Similarity": 0.0,
                "Overall NAP Status": "FAIL - No results found"
            })
            continue

        # Get the top result and detailed info
        top_result = places_result['results'][0]
        place_id = top_result['place_id']
        place_details = gmaps.place(place_id=place_id, fields=['formatted_phone_number', 'formatted_address'])['result']

        api_name = top_result.get("name", "")
        api_address = place_details.get("formatted_address", "")
        api_phone = place_details.get("formatted_phone_number", "")

        # Perform matching checks
        name_match, name_sim = check_name_match(business_name, api_name)
        address_match, address_sim = check_address_match(full_address, api_address)
        phone_match, phone_sim = check_phone_match(phone, api_phone)

        # Determine overall status
        if name_match and address_match and phone_match:
            status = "SUCCESS - All NAP data matches"
        elif name_match and address_match:
            status = "SUCCESS - Name & Address match (Phone missing/different)"
        elif name_match and phone_match:
            status = "PARTIAL - Name & Phone match (Address different)"
        elif address_match and phone_match:
            status = "PARTIAL - Address & Phone match (Name different)"
        elif name_match:
            status = "PARTIAL - Only Name matches"
        elif (name_sim >= 0.95 and address_sim >= 0.95) or (name_sim >= 0.95 and phone_sim >= 0.95):
            status = "SUCCESS - 95%+ similarity match"
        else:
            status = "FAIL - Significant NAP inconsistencies"

        results.append({
            "Input Business Name": business_name,
            "Input Phone": phone,
            "Input Address": full_address,
            "API Name": api_name,
            "API Phone": api_phone,
            "API Address": api_address,
            "Name Match": "Yes" if name_match else "No",
            "Address Match": "Yes" if address_match else "No",
            "Phone Match": "Yes" if phone_match else "No",
            "Name Similarity": round(name_sim, 3),
            "Address Similarity": round(address_sim, 3),
            "Phone Similarity": round(phone_sim, 3),
            "Overall NAP Status": status
        })

        print(f"   ✅ {status}")

    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
        results.append({
            "Input Business Name": business_name,
            "Input Phone": phone,
            "Input Address": full_address,
            "API Name": "",
            "API Phone": "",
            "API Address": "",
            "Name Match": "Error",
            "Address Match": "Error",
            "Phone Match": "Error", 
            "Name Similarity": 0.0,
            "Address Similarity": 0.0,
            "Phone Similarity": 0.0,
            "Overall NAP Status": f"ERROR - {str(e)}"
        })

# === EXPORT RESULTS ===
output_df = pd.DataFrame(results)

# Add summary statistics
success_count = len(output_df[output_df['Overall NAP Status'].str.contains('SUCCESS')])
partial_count = len(output_df[output_df['Overall NAP Status'].str.contains('PARTIAL')])
fail_count = len(output_df[output_df['Overall NAP Status'].str.contains('FAIL')])
error_count = len(output_df[output_df['Overall NAP Status'].str.contains('ERROR')])

print(f"\n📈 SUMMARY RESULTS:")
print(f"   🟢 Success: {success_count}")
print(f"   🟡 Partial: {partial_count}")
print(f"   🔴 Failed: {fail_count}")
print(f"   ⚠️  Errors: {error_count}")
print(f"   📊 Total: {len(output_df)}")

output_df.to_csv(OUTPUT_CSV, index=False)
print(f"✅ Results written to: {OUTPUT_CSV}")