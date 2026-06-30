import pandas as pd
from datetime import datetime, timezone
from app.workers.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.job import Job
from app.models.transaction import Transaction, JobSummary
from app.services.cleaner import clean_dataframe
from app.services.anomaly import detect_anomalies
from app.services.llm import classify_transactions, generate_narrative_summary

@celery_app.task
def process_csv(job_id: str, file_path: str):
    db = SessionLocal()
    try:
        # 1. Update job status to processing
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            print(f"  [task] Job {job_id} not found in database.")
            return
        
        job.status = "processing"
        db.commit()

        # 2. Read the CSV using pandas
        print(f"  [task] Starting job {job_id}, reading file: {file_path}")
        try:
            df = pd.read_csv(file_path)
        except Exception as e:
            print(f"  [task] Error reading CSV: {e}")
            job.status = "failed"
            job.error_message = f"Failed to read CSV: {str(e)}"
            db.commit()
            return

        job.row_count_raw = len(df)
        db.commit()

        # 3. Process the dataframe (clean, anomaly, classify)
        try:
            df = clean_dataframe(df)
            df = detect_anomalies(df)
            df = classify_transactions(df)
        except Exception as e:
            print(f"  [task] Error processing data: {e}")
            job.status = "failed"
            job.error_message = f"Error during data processing: {str(e)}"
            db.commit()
            return

        # 4. Save transactions
        print(f"  [task] Saving cleaned transactions to database...")
        transactions_to_add = []
        for _, row in df.iterrows():
            txn = Transaction(
                job_id=job_id,
                txn_id=str(row.get("txn_id")) if pd.notna(row.get("txn_id")) else None,
                date=str(row.get("date")) if pd.notna(row.get("date")) else None,
                merchant=str(row.get("merchant")) if pd.notna(row.get("merchant")) else None,
                amount=float(row.get("amount")) if pd.notna(row.get("amount")) else None,
                currency=str(row.get("currency")) if pd.notna(row.get("currency")) else None,
                status=str(row.get("status")) if pd.notna(row.get("status")) else None,
                category=str(row.get("category")) if pd.notna(row.get("category")) else None,
                account_id=str(row.get("account_id")) if pd.notna(row.get("account_id")) else None,
                notes=str(row.get("notes")) if pd.notna(row.get("notes")) else None,
                is_anomaly=bool(row.get("is_anomaly", False)),
                anomaly_reason=str(row.get("anomaly_reason")) if pd.notna(row.get("anomaly_reason")) else None,
                llm_category=str(row.get("llm_category")) if pd.notna(row.get("llm_category")) else None,
                llm_raw_response=str(row.get("llm_raw_response")) if pd.notna(row.get("llm_raw_response")) else None,
                llm_failed=bool(row.get("llm_failed", False)),
            )
            transactions_to_add.append(txn)
        
        # Save to database
        db.bulk_save_objects(transactions_to_add)

        # 5. Generate summary and save
        print(f"  [task] Generating narrative summary using LLM...")
        try:
            summary_data = generate_narrative_summary(df)
            summary = JobSummary(
                job_id=job_id,
                total_spend_inr=summary_data.get("total_spend_inr", 0.0),
                total_spend_usd=summary_data.get("total_spend_usd", 0.0),
                top_merchants=summary_data.get("top_merchants", []),
                anomaly_count=summary_data.get("anomaly_count", 0),
                narrative=summary_data.get("narrative", ""),
                risk_level=summary_data.get("risk_level", "medium"),
            )
            db.add(summary)
        except Exception as e:
            print(f"  [task] Error generating/saving summary: {e}")
            # Do not fail the whole job just because summary generation failed, but log it
            summary = JobSummary(
                job_id=job_id,
                total_spend_inr=0.0,
                total_spend_usd=0.0,
                top_merchants=[],
                anomaly_count=0,
                narrative=f"Summary failed: {str(e)}",
                risk_level="unknown",
            )
            db.add(summary)

        # 6. Complete the job
        job.row_count_clean = len(df)
        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        print(f"  [task] Job {job_id} successfully completed!")

    except Exception as e:
        print(f"  [task] Uncaught task error: {e}")
        db.rollback()
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = "failed"
                job.error_message = f"Uncaught exception: {str(e)}"
                db.commit()
        except Exception as db_err:
            print(f"  [task] Failed to update job error state: {db_err}")
    finally:
        db.close()