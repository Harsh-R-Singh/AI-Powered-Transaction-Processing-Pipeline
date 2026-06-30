import os, shutil
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.config import settings
from app.models.job import Job
from app.models.transaction import Transaction,JobSummary
from app.workers.tasks import process_csv

router = APIRouter(prefix="/jobs", tags=["jobs"])

@router.post("/upload")
def upload_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):

    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(settings.UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    job = Job(filename=file.filename, status="pending")
    db.add(job)
    db.commit()
    db.refresh(job)

    process_csv.delay(job.id, file_path)

    return {"job_id": job.id, "status": "pending", "filename":file.filename}


@router.get("/{job_id}/status")
def get_status(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id ==job_id).first()
    if not job:
        raise HTTPException(status_code=404,detail="Job not found.")

    response = {
        "job_id": job.id,
        "status": job.status,
        "filename": job.filename,
        "created_at": str(job.created_at),
    }

    if job.status == "completed":
        summary = db.query(JobSummary).filter(JobSummary.job_id == job_id).first()
        if summary:
            response["summary"] = {
                "total_spend_inr": summary.total_spend_inr,
                "total_spend_usd": summary.total_spend_usd,
                "anomaly_count":   summary.anomaly_count,
                "risk_level":      summary.risk_level,
                "narrative":       summary.narrative,
            }
    return response

@router.get("/{job_id}/results")
def get_results(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id ==job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job.status != "completed":
        raise HTTPException(status_code=400, detail=f"Job is not completed yet. Status: {job.status}")
 
    transactions = db.query(Transaction).filter(Transaction.job_id == job_id).all()
    summary      = db.query(JobSummary).filter(JobSummary.job_id == job_id).first()
 
    # Per-category spend breakdown
    category_spend = {}
    for txn in transactions:
        if txn.category and txn.amount:
            category_spend[txn.category] = round(
                category_spend.get(txn.category, 0) + txn.amount, 2
            )
 
    return {
        "job_id": job_id,
        "row_count_raw":   job.row_count_raw,
        "row_count_clean": job.row_count_clean,
        "transactions": [
            {
                "txn_id":         t.txn_id,
                "date":           t.date,
                "merchant":       t.merchant,
                "amount":         t.amount,
                "currency":       t.currency,
                "status":         t.status,
                "category":       t.category,
                "account_id":     t.account_id,
                "notes":          t.notes,
                "is_anomaly":     t.is_anomaly,
                "anomaly_reason": t.anomaly_reason,
                "llm_category":   t.llm_category,
                "llm_failed":     t.llm_failed,
            }
            for t in transactions
        ],
        "anomalies": [
            {
                "txn_id":   t.txn_id,
                "merchant": t.merchant,
                "amount":   t.amount,
                "reason":   t.anomaly_reason,
            }
            for t in transactions if t.is_anomaly
        ],
        "category_spend": category_spend,
        "summary": {
            "total_spend_inr": summary.total_spend_inr if summary else 0,
            "total_spend_usd": summary.total_spend_usd if summary else 0,
            "top_merchants":   summary.top_merchants   if summary else [],
            "anomaly_count":   summary.anomaly_count   if summary else 0,
            "narrative":       summary.narrative        if summary else "",
            "risk_level":      summary.risk_level       if summary else "",
        }
    }


@router.get("")
def list_jobs(status: str = Query(None), db: Session = Depends(get_db)):
    query = db.query(Job)
    if status:
        query = query.filter(Job.status == status)
    jobs = query.order_by(Job.created_at.desc()).all()
    return [
        {
            "job_id":          j.id,
            "filename":        j.filename,
            "status":          j.status,
            "row_count_raw":   j.row_count_raw,
            "row_count_clean": j.row_count_clean,
            "created_at":      str(j.created_at),
        }
        for j in jobs
    ]