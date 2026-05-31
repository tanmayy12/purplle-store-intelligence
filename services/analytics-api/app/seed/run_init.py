import csv
import logging
import time
from collections import defaultdict
from datetime import date, datetime

import yaml
from dateutil import parser as date_parser
from sqlalchemy.orm import Session

from app.config import settings
from app.consumers.tracking_consumer import create_topics
from app.database import SessionLocal, init_db
from app.models import PosLineItem, PosTransaction, Store, Zone

logger = logging.getLogger(__name__)


def wait_for_postgres(max_retries: int = 30, delay: float = 2.0) -> None:
    for attempt in range(max_retries):
        try:
            from sqlalchemy import text

            db = SessionLocal()
            db.execute(text("SELECT 1"))
            db.close()
            logger.info("PostgreSQL is ready")
            return
        except Exception as exc:
            logger.info("Waiting for PostgreSQL (%d/%d): %s", attempt + 1, max_retries, exc)
            time.sleep(delay)
    raise RuntimeError("PostgreSQL not available")


def wait_for_kafka(max_retries: int = 30, delay: float = 2.0) -> None:
    for attempt in range(max_retries):
        try:
            create_topics()
            logger.info("Kafka/Redpanda is ready")
            return
        except Exception as exc:
            logger.info("Waiting for Kafka (%d/%d): %s", attempt + 1, max_retries, exc)
            time.sleep(delay)
    raise RuntimeError("Kafka not available")


def seed_store(db: Session) -> None:
    existing = db.query(Store).filter(Store.store_id == settings.store_id).first()
    if existing:
        return
    store = Store(
        store_id=settings.store_id,
        store_name=settings.store_name,
        city="Bangalore",
        timezone="Asia/Kolkata",
        operating_date=date.fromisoformat(settings.operating_date),
    )
    db.add(store)
    db.commit()
    logger.info("Seeded store %s", settings.store_id)


def seed_zones(db: Session) -> None:
    if db.query(Zone).count() > 0:
        return

    with open(settings.zones_config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    for zone_def in config.get("zones", []):
        zone = Zone(
            zone_id=zone_def["zone_id"],
            store_id=settings.store_id,
            zone_name=zone_def["zone_name"],
            zone_type=zone_def.get("zone_type"),
            department_map=zone_def.get("department_map"),
            polygon_json=zone_def.get("polygon"),
            is_staff_only=zone_def.get("is_staff_only", False),
            priority=zone_def.get("priority", 0),
        )
        db.add(zone)
    db.commit()
    logger.info("Seeded %d zones", len(config.get("zones", [])))


def seed_pos(db: Session) -> None:
    if db.query(PosTransaction).count() > 0:
        logger.info("POS data already seeded")
        return

    invoices: dict[str, dict] = defaultdict(lambda: {"lines": [], "nmv": 0, "qty": 0, "depts": set()})

    with open(settings.pos_csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            inv = row["invoice_number"]
            invoices[inv]["order_id"] = row["order_id"]
            invoices[inv]["time"] = row["order_time"]
            invoices[inv]["date"] = row["order_date"]
            invoices[inv]["customer"] = row["customer_name"].strip()
            invoices[inv]["salesperson_id"] = row["salesperson_id"]
            invoices[inv]["salesperson_name"] = row["salesperson_name"]
            invoices[inv]["lines"].append(row)
            invoices[inv]["nmv"] += float(row["NMV"] or 0)
            invoices[inv]["qty"] += int(row["qty"] or 0)
            invoices[inv]["depts"].add(row["dep_name"])

    for invoice_number, data in invoices.items():
        dt_str = f"{data['date']} {data['time']}"
        transaction_at = date_parser.parse(dt_str, dayfirst=True)
        txn = PosTransaction(
            order_id=data["order_id"],
            invoice_number=invoice_number,
            store_id=settings.store_id,
            transaction_at=transaction_at,
            nmv=round(data["nmv"], 2),
            item_count=data["qty"],
            departments=sorted(data["depts"]),
            salesperson_id=data["salesperson_id"],
            salesperson_name=data["salesperson_name"],
            customer_name=data["customer"],
            raw_payload={"line_count": len(data["lines"])},
        )
        db.add(txn)
        db.flush()

        for row in data["lines"]:
            db.add(
                PosLineItem(
                    order_id=row["order_id"],
                    invoice_number=invoice_number,
                    sku=row["sku"],
                    product_name=row["product_name"],
                    brand_name=row["brand_name"],
                    dep_name=row["dep_name"],
                    sub_category=row["sub_category"],
                    qty=int(row["qty"] or 0),
                    nmv=float(row["NMV"] or 0),
                )
            )

    db.commit()
    logger.info("Seeded %d POS transactions", len(invoices))


def run() -> None:
    logging.basicConfig(level=settings.log_level)
    logger.info("Starting init-seed job")

    wait_for_postgres()
    wait_for_kafka()
    init_db()

    db = SessionLocal()
    try:
        seed_store(db)
        seed_zones(db)
        seed_pos(db)
    finally:
        db.close()

    logger.info("Init-seed completed successfully")


if __name__ == "__main__":
    run()
