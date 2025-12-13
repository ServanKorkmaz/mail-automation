"""Reorganize schools.csv for better readability."""
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def reorganize_csv(csv_path: str = "schools.csv"):
    """Reorganize CSV file for better overview."""
    # Read existing CSV
    df = pd.read_csv(csv_path, encoding='utf-8-sig')
    
    logger.info(f"Loaded {len(df)} schools from {csv_path}")
    
    # Filter out invalid school names
    invalid_patterns = [
        "istanbul ortaokulları", "istanbul ortaokullar",
        "aradığınız", "görüntüleyin", "detaylarını",
        "tüm detaylar", "giriş yap", "devamını",
        "okul listesi", "school list", "sayfa", "page"
    ]
    
    def is_valid_school_name(name: str) -> bool:
        if pd.isna(name) or not name or len(str(name)) < 5:
            return False
        name_lower = str(name).lower()
        return not any(pattern in name_lower for pattern in invalid_patterns)
    
    original_count = len(df)
    df = df[df["name"].apply(is_valid_school_name)].copy()
    removed = original_count - len(df)
    
    if removed > 0:
        logger.info(f"Removed {removed} invalid entries")
    
    # Ensure contacted column exists
    if "contacted" not in df.columns:
        df["contacted"] = "no"
    
    # Sort by priority:
    # 1. Schools with email (most important)
    # 2. Schools with website
    # 3. Alphabetically by name
    df["_has_email"] = df["email"].apply(lambda x: 0 if pd.isna(x) or x == "NOT FOUND" or x == "" else 1)
    df["_has_website"] = df["website"].apply(lambda x: 0 if pd.isna(x) or x == "" else 1)
    df["_name_sort"] = df["name"].str.lower()
    
    df = df.sort_values(
        ["_has_email", "_has_website", "_name_sort"],
        ascending=[False, False, True]
    ).drop(["_has_email", "_has_website", "_name_sort"], axis=1)
    
    # Reset index
    df = df.reset_index(drop=True)
    
    # Save with UTF-8-sig encoding (Excel compatible)
    df.to_csv(csv_path, index=False, encoding='utf-8-sig')
    
    # Print statistics
    total = len(df)
    with_email = len(df[df["email"].notna() & (df["email"] != "NOT FOUND") & (df["email"] != "")])
    with_website = len(df[df["website"].notna() & (df["website"] != "")])
    contacted = len(df[df["contacted"].str.lower() == "yes"])
    not_contacted_with_email = len(df[
        (df["email"].notna()) & 
        (df["email"] != "NOT FOUND") & 
        (df["email"] != "") &
        (df["contacted"].str.lower() != "yes")
    ])
    
    print("\n" + "=" * 60)
    print("CSV REORGANIZATION COMPLETE")
    print("=" * 60)
    print(f"Total schools: {total}")
    print(f"  - With email: {with_email}")
    print(f"  - With website: {with_website}")
    print(f"  - Already contacted: {contacted}")
    print(f"  - Ready to contact: {not_contacted_with_email}")
    print("=" * 60)
    print(f"\nFile saved: {csv_path}")
    print("\nSchools are sorted by:")
    print("  1. Has email (highest priority)")
    print("  2. Has website")
    print("  3. Alphabetically by name")


if __name__ == "__main__":
    reorganize_csv()

