"""SQL query helpers for core-api. All raw SQL via text()."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


def list_facilities(session: Session) -> list[dict]:
    rows = session.execute(text(
        "SELECT id, name, level, lat, lon, cold_storage_ok, cold_storage_note, "
        "report_format, report_lang, taluk FROM facility ORDER BY id"
    )).fetchall()
    return [
        {
            "id": r.id,
            "name": r.name,
            "type": "warehouse" if r.level == "WH" else "hospital",
            "level": r.level,
            "lat": float(r.lat),
            "lon": float(r.lon),
            "cold_storage": bool(r.cold_storage_ok),
        }
        for r in rows
    ]


def list_drugs(session: Session) -> list[dict]:
    rows = session.execute(text(
        "SELECT code, name, ven, unit, pack_size, cold_chain, controlled, "
        "min_residual_days, unit_cost_inr, temp_min_c, temp_max_c FROM drug ORDER BY code"
    )).fetchall()
    return [
        {
            "code": r.code,
            "name": r.name,
            "ven": r.ven.strip(),
            "unit": r.unit,
            "pack_size": r.pack_size,
            "cold_chain": bool(r.cold_chain),
            "controlled": bool(r.controlled),
            "min_residual_days": r.min_residual_days,
            "unit_cost_inr": float(r.unit_cost_inr),
        }
        for r in rows
    ]


def list_routes(session: Session) -> list[dict]:
    rows = session.execute(text(
        "SELECT src_facility_id, dst_facility_id, distance_km, transit_hours, "
        "cold_capable, cost_ambient_inr, cost_cold_inr FROM route "
        "ORDER BY src_facility_id, dst_facility_id"
    )).fetchall()
    return [
        {
            "src_facility_id": r.src_facility_id,
            "dst_facility_id": r.dst_facility_id,
            "distance_km": float(r.distance_km),
            "transit_hours": float(r.transit_hours),
            "cold_chain": bool(r.cold_capable),
            "cost_ambient_inr": float(r.cost_ambient_inr),
            "cost_cold_inr": float(r.cost_cold_inr),
        }
        for r in rows
    ]


def list_vehicles(session: Session) -> list[dict]:
    rows = session.execute(text(
        "SELECT id, name, type, cold_chain, capacity_units FROM vehicle ORDER BY id"
    )).fetchall()
    return [
        {
            "id": r.id,
            "name": r.name,
            "type": r.type,
            "cold_chain": bool(r.cold_chain),
            "capacity_units": r.capacity_units,
        }
        for r in rows
    ]


def list_lots(session: Session, facility: str | None = None, drug: str | None = None) -> list[dict]:
    sql = "SELECT facility_id, drug_code, batch_no, expiry, qty FROM lot WHERE 1=1"
    params: dict = {}
    if facility:
        sql += " AND facility_id = :facility"
        params["facility"] = facility
    if drug:
        sql += " AND drug_code = :drug"
        params["drug"] = drug
    sql += " ORDER BY facility_id, drug_code, expiry"
    rows = session.execute(text(sql), params).fetchall()
    return [
        {
            "facility_id": r.facility_id,
            "drug_code": r.drug_code,
            "batch_no": r.batch_no,
            "expiry": r.expiry.isoformat() if hasattr(r.expiry, "isoformat") else str(r.expiry),
            "qty": r.qty,
        }
        for r in rows
    ]


def list_policies(session: Session) -> list[dict]:
    rows = session.execute(text(
        "SELECT facility_id, drug_code, min_reserve_days, target_days, "
        "max_stock_days, lead_time_days FROM policy ORDER BY facility_id, drug_code"
    )).fetchall()
    return [
        {
            "facility_id": r.facility_id,
            "drug_code": r.drug_code,
            "min_reserve_days": r.min_reserve_days,
            "target_days": r.target_days,
            "max_stock_days": r.max_stock_days,
            "lead_time_days": r.lead_time_days,
        }
        for r in rows
    ]


def get_policy(session: Session, facility_id: str, drug_code: str) -> dict:
    row = session.execute(text(
        "SELECT min_reserve_days, target_days, lead_time_days "
        "FROM policy WHERE facility_id = :fac AND drug_code = :drug"
    ), {"fac": facility_id, "drug": drug_code}).fetchone()
    if row:
        return {
            "min_reserve_days": row.min_reserve_days,
            "target_days": row.target_days,
            "lead_time_days": row.lead_time_days,
        }
    return {"min_reserve_days": 7, "target_days": 21, "lead_time_days": 3}


def get_consumption_rate(session: Session, facility_id: str, drug_code: str, today) -> float:
    row = session.execute(text(
        "SELECT adjusted_rate FROM forecast "
        "WHERE facility_id = :fac AND drug_code = :drug"
    ), {"fac": facility_id, "drug": drug_code}).fetchone()
    if row:
        return float(row.adjusted_rate)
    row = session.execute(text(
        "SELECT COALESCE(AVG(qty), 0) as avg_rate FROM consumption_daily "
        "WHERE facility_id = :fac AND drug_code = :drug "
        "AND date >= :since"
    ), {
        "fac": facility_id,
        "drug": drug_code,
        "since": (today - __import__("datetime").timedelta(days=28)).isoformat(),
    }).fetchone()
    return float(row.avg_rate) if row else 0.0


def list_forecasts(session: Session) -> list[dict]:
    rows = session.execute(text(
        "SELECT facility_id, drug_code, horizon_days, daily_rate, method, "
        "confidence, context_multiplier, adjusted_rate FROM forecast "
        "ORDER BY facility_id, drug_code"
    )).fetchall()
    return [
        {
            "facility_id": r.facility_id,
            "drug_code": r.drug_code,
            "horizon_days": r.horizon_days,
            "daily_rate": float(r.daily_rate),
            "method": r.method,
            "confidence": float(r.confidence),
            "context_multiplier": float(r.context_multiplier),
            "adjusted_rate": float(r.adjusted_rate),
        }
        for r in rows
    ]


def facility_drug_groups(session: Session) -> list[tuple[str, str]]:
    rows = session.execute(text(
        "SELECT DISTINCT facility_id, drug_code FROM lot ORDER BY facility_id, drug_code"
    )).fetchall()
    return [(r.facility_id, r.drug_code) for r in rows]


def get_lots_for_position(session: Session, facility_id: str, drug_code: str) -> list[dict]:
    rows = session.execute(text(
        "SELECT batch_no, expiry, qty FROM lot "
        "WHERE facility_id = :fac AND drug_code = :drug AND qty > 0 "
        "ORDER BY expiry"
    ), {"fac": facility_id, "drug": drug_code}).fetchall()
    return [
        {
            "batch_no": r.batch_no,
            "expiry": r.expiry if hasattr(r.expiry, "year") else __import__("datetime").date.fromisoformat(str(r.expiry)),
            "qty": r.qty,
        }
        for r in rows
    ]


def upsert_lot(session: Session, lot: dict) -> tuple[int, int]:
    row = session.execute(text(
        "SELECT qty FROM lot WHERE facility_id = :fac AND drug_code = :drug AND batch_no = :batch"
    ), {"fac": lot["facility_id"], "drug": lot["drug_code"], "batch": lot["batch_no"]}).fetchone()
    old_qty = row.qty if row else 0

    session.execute(text(
        "INSERT INTO lot (facility_id, drug_code, batch_no, expiry, qty) "
        "VALUES (:fac, :drug, :batch, :expiry, :qty) "
        "ON CONFLICT (facility_id, drug_code, batch_no) "
        "DO UPDATE SET qty = EXCLUDED.qty, expiry = EXCLUDED.expiry"
    ), {
        "fac": lot["facility_id"],
        "drug": lot["drug_code"],
        "batch": lot["batch_no"],
        "expiry": lot["expiry"],
        "qty": lot["qty"],
    })
    return old_qty, lot["qty"]


def get_next_dta_seq(session: Session) -> int:
    row = session.execute(text(
        "SELECT COALESCE(MAX(CAST(SPLIT_PART(dta_number, '/', 4) AS INTEGER)), 0) + 1 "
        "AS next_seq FROM transfer_order"
    )).fetchone()
    return row.next_seq if row else 1


def insert_plan_run(session: Session, plan: dict) -> None:
    session.execute(text(
        "INSERT INTO plan_run (id, mode, solver_tier, energy, gap_to_milp, "
        "variables, constraints, transfers, shortage_reduction, expiry_avoided, "
        "cost_inr, params) "
        "VALUES (:id, :mode, :solver_tier, :energy, :gap_to_milp, "
        ":variables, :constraints, :transfers, :shortage_reduction, "
        ":expiry_avoided, :cost_inr, CAST(:params AS JSONB))"
    ), {
        "id": plan["id"],
        "mode": plan.get("mode", "live"),
        "solver_tier": plan["solver_tier"],
        "energy": plan.get("energy"),
        "gap_to_milp": plan.get("gap_to_milp"),
        "variables": plan.get("variables", 0),
        "constraints": plan.get("constraints", 0),
        "transfers": plan.get("transfers", 0),
        "shortage_reduction": plan.get("shortage_reduction"),
        "expiry_avoided": plan.get("expiry_avoided"),
        "cost_inr": plan.get("cost_inr"),
        "params": __import__("json").dumps(plan.get("params") or {}),
    })


def insert_candidate(session: Session, plan_run_id: str, c: dict) -> None:
    session.execute(text(
        "INSERT INTO candidate (plan_run_id, chunk_id, facility_id, drug_code, "
        "batch_no, destination_id, usable, score, feasibility, selected) "
        "VALUES (:plan_run_id, :chunk_id, :fac, :drug, :batch, :dest, "
        ":usable, :score, CAST(:feasibility AS JSONB), :selected)"
    ), {
        "plan_run_id": plan_run_id,
        "chunk_id": c.get("chunk_id"),
        "fac": c["lot"]["facility_id"] if "lot" in c else c.get("facility_id"),
        "drug": c.get("drug_code") or (c["lot"]["drug_code"] if "lot" in c else ""),
        "batch": c["lot"]["batch_no"] if "lot" in c else c.get("batch_no", ""),
        "dest": c["destination_id"],
        "usable": c["usable"],
        "score": c["score"],
        "feasibility": __import__("json").dumps(c.get("feasibility") or {}),
        "selected": c.get("selected", False),
    })


def insert_transfer_order(session: Session, order: dict) -> None:
    session.execute(text(
        "INSERT INTO transfer_order (id, dta_number, plan_run_id, src_facility_id, "
        "dst_facility_id, drug_code, drug_name, batch_no, qty, usable, score, "
        "status, temperature_req) "
        "VALUES (:id, :dta, :plan, :src, :dst, :drug, :drug_name, :batch, "
        ":qty, :usable, :score, :status, :temp_req)"
    ), {
        "id": order["id"],
        "dta": order["dta_number"],
        "plan": order["plan_id"],
        "src": order["src_facility_id"],
        "dst": order["dst_facility_id"],
        "drug": order["drug_code"],
        "drug_name": order["drug_name"],
        "batch": order["batch_no"],
        "qty": order["qty"],
        "usable": order["usable"],
        "score": order.get("score"),
        "status": order.get("status", "proposed"),
        "temp_req": order.get("temperature_req", "ambient"),
    })


def insert_regret(session: Session, plan_run_id: str, r: dict) -> None:
    session.execute(text(
        "INSERT INTO regret_entry (plan_run_id, order_id, alternative, reason, delta_score) "
        "VALUES (:plan, :order_id, :alt, :reason, :delta)"
    ), {
        "plan": plan_run_id,
        "order_id": r.get("order_id"),
        "alt": r.get("alternative", ""),
        "reason": r["reason"],
        "delta": r.get("score_delta", 0),
    })


def list_orders(session: Session, plan_id: str | None = None, status: str | None = None) -> list[dict]:
    sql = (
        "SELECT id, dta_number, plan_run_id, src_facility_id, dst_facility_id, "
        "drug_code, drug_name, batch_no, qty, usable, score, status, "
        "temperature_req, vehicle_id, approved_by, approved_at, rejected_reason, "
        "created_at FROM transfer_order WHERE 1=1"
    )
    params: dict = {}
    if plan_id:
        sql += " AND plan_run_id = :plan_id"
        params["plan_id"] = plan_id
    if status:
        sql += " AND status = :status"
        params["status"] = status
    sql += " ORDER BY created_at"
    return [_order_row_to_dict(r) for r in session.execute(text(sql), params).fetchall()]


def get_order(session: Session, order_id: str) -> dict | None:
    row = session.execute(text(
        "SELECT id, dta_number, plan_run_id, src_facility_id, dst_facility_id, "
        "drug_code, drug_name, batch_no, qty, usable, score, status, "
        "temperature_req, vehicle_id, approved_by, approved_at, rejected_reason, "
        "created_at FROM transfer_order WHERE id = :id"
    ), {"id": order_id}).fetchone()
    return _order_row_to_dict(row) if row else None


def _order_row_to_dict(r) -> dict:
    return {
        "id": r.id,
        "dta_number": r.dta_number,
        "plan_id": r.plan_run_id,
        "src_facility_id": r.src_facility_id,
        "dst_facility_id": r.dst_facility_id,
        "drug_code": r.drug_code,
        "drug_name": r.drug_name,
        "batch_no": r.batch_no,
        "qty": r.qty,
        "usable": r.usable,
        "score": float(r.score) if r.score is not None else None,
        "status": r.status,
        "temperature_req": r.temperature_req,
        "created_at": r.created_at.isoformat() if hasattr(r.created_at, "isoformat") else str(r.created_at),
    }


def approve_order(session: Session, order_id: str, actor: str, now) -> dict | None:
    session.execute(text(
        "UPDATE transfer_order SET status = 'approved', approved_by = :actor, "
        "approved_at = :now WHERE id = :id AND status = 'proposed'"
    ), {"id": order_id, "actor": actor, "now": now})
    return get_order(session, order_id)


def reject_order(session: Session, order_id: str, reason: str, now) -> dict | None:
    session.execute(text(
        "UPDATE transfer_order SET status = 'rejected', rejected_reason = :reason, "
        "approved_at = :now WHERE id = :id AND status = 'proposed'"
    ), {"id": order_id, "reason": reason, "now": now})
    return get_order(session, order_id)


def get_custody_events(session: Session, order_id: str) -> list[dict]:
    rows = session.execute(text(
        "SELECT order_id, event_type, actor, timestamp, location, "
        "temperature_c, notes FROM custody_event "
        "WHERE order_id = :oid ORDER BY timestamp"
    ), {"oid": order_id}).fetchall()
    return [
        {
            "order_id": r.order_id,
            "event_type": r.event_type,
            "actor": r.actor,
            "timestamp": r.timestamp.isoformat() if hasattr(r.timestamp, "isoformat") else str(r.timestamp),
            "location": r.location,
            "temperature_c": float(r.temperature_c) if r.temperature_c is not None else None,
            "notes": r.notes,
        }
        for r in rows
    ]


def get_audit_entries(session: Session, entity: str | None = None, entity_id: str | None = None) -> list[dict]:
    sql = "SELECT seq, actor, action, entity, entity_id, payload, hash, created_at FROM audit_log WHERE 1=1"
    params: dict = {}
    if entity:
        sql += " AND entity = :entity"
        params["entity"] = entity
    if entity_id:
        sql += " AND entity_id = :entity_id"
        params["entity_id"] = entity_id
    sql += " ORDER BY seq"
    rows = session.execute(text(sql), params).fetchall()
    return [
        {
            "seq": r.seq,
            "actor": r.actor,
            "action": r.action,
            "entity": r.entity,
            "entity_id": r.entity_id,
            "payload": r.payload if isinstance(r.payload, dict) else __import__("json").loads(r.payload),
            "hash": r.hash,
            "created_at": r.created_at.isoformat() if hasattr(r.created_at, "isoformat") else str(r.created_at),
        }
        for r in rows
    ]


def get_provenance(session: Session, order_id: str) -> dict | None:
    order = get_order(session, order_id)
    if not order:
        return None

    custody = get_custody_events(session, order_id)
    audit = get_audit_entries(session, entity="order", entity_id=order_id)

    return {
        "order": order,
        "custody": custody,
        "audit": audit,
    }
