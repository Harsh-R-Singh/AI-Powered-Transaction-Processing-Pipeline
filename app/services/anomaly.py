import pandas as pd

DOMESTIC_ONLY = {
    "swiggy", "zomato", "ola", "irctc",
    "bigbasket", "blinkit", "jio recharge", "bookmyshow"
}

def detect_anomalies(df):
    df["is_anomaly"] = False
    df["anomaly_reason"] = None

    medians = df.groupby("account_id")["amount"].median()
    for idx,row in df.iterrows():
        if pd.isna(row["amount"]) or pd.isna(row["account_id"]):
            continue
        median = medians.get(row["account_id"],0)
        if median and row["amount"] > 3 * median:
            df.at[idx, "is_anomaly"] = True
            df.at[idx,"anomaly_reason"] = (
                f"Amount {row['amount']:.2f} exceeds 3x"
                f"account median {median:.2f}"
            )

    for idx, row in df.iterrows():
        if str(row.get("currency", "")).upper() != "USD":
            continue
        merchant = str(row.get("merchant", "")).lower().strip()
        if any(d in merchant for d in DOMESTIC_ONLY):
            reason   = f"USD used at domestic-only merchant '{row['merchant']}'"
            existing = df.at[idx, "anomaly_reason"]
            df.at[idx, "is_anomaly"]     = True
            df.at[idx, "anomaly_reason"] = f"{existing}; {reason}" if existing else reason

    print(f"  [anomaly] Flagged {int(df['is_anomaly'].sum())} anomalies")
    return df
