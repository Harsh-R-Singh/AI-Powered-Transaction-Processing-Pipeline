import uuid,re
import pandas as pd

def normalise_dates(df):
    def parse_date(val):
        if pd.isna(val) or str(val).strip() == "":
            return None
        val = str(val).strip()
        for fmt in ["%d-%m-%Y","%Y/%m/%d","%d-%b-%Y","%d-%m","%d-%b-%Y","%d-%m-%Y","%m-%d-%Y"]:
            try:
                return pd.to_datetime(val, format=fmt).strftime("%Y-%m-%d")
            except ValueError:
                pass
        try:
            return pd.to_datetime(val).strftime("%Y-%m-%d")
        except Exception:
            return None

    df["date"] = df["date"].apply(parse_date)
    return df

def clean_amounts(df):
    def parse_amount(val):
        if pd.isna(val):
            return None
        cleaned = re.sub(r"[$,\s]", "", str(val))
        try:
            return float(cleaned)
        except ValueError:
            return None
    df["amount"] = df["amount"].apply(parse_amount)
    return df

def uppercase_fields(df):
    for col in ["currency", "status"]:
        if col in df.columns:
            df[col] = df[col].str.upper().str.strip()
    return df

def fill_missing_categories(df):
    df["category"] = df["category"].fillna("Uncategorised").str.strip()
    df.loc[df["category"] == "", "category"] = "Uncategorised"
    return df

def remove_duplicates(df):
    before = len(df)
    df = df.drop_duplicates()
    print(f"  [cleaner] Removed {before - len(df)} duplicate rows")
    return df

def generate_missing_txn_ids(df):
    mask = df["txn_id"].isna() | (df["txn_id"].astype(str).str.strip() == "")
    df.loc[mask, "txn_id"] = [
        f"GEN-{uuid.uuid4().hex[:8].upper()}" for _ in range(mask.sum())
    ]
    return df

def clean_dataframe(df):
    print(f"  [cleaner] Starting with {len(df)} rows")
    df = remove_duplicates(df)
    df = normalise_dates(df)
    df = clean_amounts(df)
    df = uppercase_fields(df)
    df = fill_missing_categories(df)
    df = generate_missing_txn_ids(df)
    print(f"  [cleaner] Finished with {len(df)} rows")
    return df
        