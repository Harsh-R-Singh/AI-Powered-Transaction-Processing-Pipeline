import json, time, pandas as pd
from google import genai
from app.core.config import settings
import traceback
VALID_CATEGORIES = ["Food","Shopping","Travel","Transport","Utilities","Cash Withdrawal","Entertainment","Other"]

# One shared client. The official SDK handles whatever key format
# Google issues (old AIzaSy... or the new AQ... auth key) automatically.
_client = genai.Client(api_key=settings.GEMINI_API_KEY)

import traceback

def call_gemini(prompt, max_retries=3):
    for attempt in range(1, max_retries + 1):
        try:
            response = _client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )

            print("\n================ GEMINI RESPONSE ================")
            print(response.text)
            print("=================================================\n")

            return response.text.strip()

        except Exception as e:
            print("\n================ GEMINI ERROR ===================")
            traceback.print_exc()
            print("=================================================\n")

            wait = 2 ** attempt
            print(f"[llm] Attempt {attempt} failed. Retrying in {wait}s")

            if attempt < max_retries:
                time.sleep(wait)

    print("[llm] All retries failed.")
    return None

def classify_transactions(df):
    df["llm_category"]     = None
    df["llm_raw_response"] = None
    df["llm_failed"]       = False

    mask          = df["category"] == "Uncategorised"
    uncategorised = df[mask]
    if uncategorised.empty:
        return df

    indices = uncategorised.index.tolist()
    for batch_start in range(0, len(indices), 20):
        batch_indices = indices[batch_start:batch_start + 20]
        batch         = df.loc[batch_indices]

        rows_text = "\n".join(
            f"{i+1}. merchant={row['merchant']}, amount={row['amount']}, notes={row['notes']}"
            for i, (_, row) in enumerate(batch.iterrows())
        )
        prompt = f"""Classify each transaction into ONE of: {', '.join(VALID_CATEGORIES)}

Transactions:
{rows_text}

Reply ONLY with a JSON array like: [{{"index":1,"category":"Food"}}]
No markdown, no explanation."""

        raw = call_gemini(prompt)
        if raw is None:
            df.loc[batch_indices, "llm_failed"] = True
            continue
        try:
            cleaned = raw.replace("```json", "").replace("```", "").strip()
            results = json.loads(cleaned)
            for item in results:
                pos = item["index"] - 1
                if pos < len(batch_indices):
                    real_idx = batch_indices[pos]
                    cat      = item.get("category", "Other")
                    df.at[real_idx, "llm_category"]     = cat if cat in VALID_CATEGORIES else "Other"
                    df.at[real_idx, "llm_raw_response"] = raw
        except Exception as e:
            print(f"  [llm] Parse error: {e}")
            df.loc[batch_indices, "llm_failed"] = True

    print(f"  [llm] Classified {df['llm_category'].notna().sum()} transactions")
    return df

def generate_narrative_summary(df):
    inr_total     = float(df[df["currency"] == "INR"]["amount"].sum())
    usd_total     = float(df[df["currency"] == "USD"]["amount"].sum())
    anomaly_count = int(df["is_anomaly"].sum())
    top_merchants = (
        df.groupby("merchant")["amount"].sum()
        .sort_values(ascending=False).head(3)
        .reset_index().rename(columns={"amount": "total"})
        .to_dict(orient="records")
    )
    prompt = f"""You are a financial analyst. Summarise this transaction data:
- Total INR spend: {inr_total:.2f}
- Total USD spend: {usd_total:.2f}
- Total transactions: {len(df)}
- Anomalies flagged: {anomaly_count}
- Top merchants: {top_merchants}
- Categories: {df['category'].value_counts().to_dict()}

Return ONLY this JSON:
{{"narrative": "2-3 sentences about spending", "risk_level": "low/medium/high"}}

Risk guide: low = fewer than 2 anomalies, medium = 2 to 5, high = more than 5."""

    raw     = call_gemini(prompt)
    default = {"narrative": "Summary unavailable.", "risk_level": "medium"}
    if raw:
        try:
            result = json.loads(raw.strip().strip("```json").strip("```").strip())
        except Exception as e:
            print("JSON Parsing Error:", e)
            print("Raw Response:")
            print(raw)
            result = default
    else:
        result = default

    return {
        "total_spend_inr": round(inr_total, 2),
        "total_spend_usd": round(usd_total, 2),
        "top_merchants":   top_merchants,
        "anomaly_count":   anomaly_count,
        "narrative":       result.get("narrative", default["narrative"]),
        "risk_level":      result.get("risk_level", "medium"),
    }
