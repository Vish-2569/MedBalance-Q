# Redis Streams Events

All events are published to Redis Streams via `medbal_common.bus.publish(stream, data)`.
Consumer groups per service.

## Streams

### report.received
Published by: ingest-ai
Consumed by: core-api, forecast
Payload:
- facility_code: string
- report_id: string
- items_count: integer
- received_at: string (ISO datetime)

Example:
```json
{"facility_code": "H1", "report_id": "rpt-001", "items_count": 5, "received_at": "2026-11-01T09:00:00+05:30"}
```

### inventory.updated
Published by: core-api
Consumed by: optimizer, forecast
Payload:
- facility_id: string
- drug_code: string
- old_qty: integer
- new_qty: integer
- reason: string (ingest|transfer|consumption|adjustment)

Example:
```json
{"facility_id": "H1", "drug_code": "PARA500", "old_qty": 200, "new_qty": 150, "reason": "consumption"}
```

### anomaly.flagged
Published by: ingest-ai
Consumed by: core-api (review queue)
Payload:
- report_id: string
- item_index: integer
- anomaly_type: string (quantity_spike|unknown_drug|expired_lot|duplicate)
- severity: string (low|medium|high)
- details: string

Example:
```json
{"report_id": "rpt-001", "item_index": 2, "anomaly_type": "quantity_spike", "severity": "high", "details": "Qty 9999 for PARA500 exceeds 3σ of historical range"}
```

### forecast.updated
Published by: forecast
Consumed by: optimizer
Payload:
- facility_id: string
- drug_code: string
- daily_rate: number
- adjusted_rate: number
- method: string

Example:
```json
{"facility_id": "H1", "drug_code": "PARA500", "daily_rate": 8.0, "adjusted_rate": 9.6, "method": "holt_winters_llm"}
```

### coldchain.alert
Published by: coldchain
Consumed by: core-api, optimizer
Payload:
- device_id: string
- vehicle_id: string
- alert_type: string (excursion|battery_low|offline)
- temperature_c: number or null
- threshold_c: number or null
- timestamp: string (ISO datetime)

Example:
```json
{"device_id": "sensor-01", "vehicle_id": "V1", "alert_type": "excursion", "temperature_c": 9.2, "threshold_c": 8.0, "timestamp": "2026-11-01T11:00:00+05:30"}
```

### plan.progress
Published by: optimizer
Consumed by: core-api (SSE relay)
Payload:
- plan_id: string
- stage: string (positions|feasibility|qubo_build|solving|validation)
- progress_pct: integer (0-100)
- message: string

Example:
```json
{"plan_id": "plan-demo-001", "stage": "solving", "progress_pct": 65, "message": "QpiAI Opt solving QUBO (42 variables)"}
```

### plan.completed
Published by: optimizer
Consumed by: core-api
Payload:
- plan_id: string
- transfers: integer
- shortage_reduction: number
- solver_tier: string
- energy: number

Example:
```json
{"plan_id": "plan-demo-001", "transfers": 6, "shortage_reduction": 0.72, "solver_tier": "qpiai-opt-local", "energy": -4.82}
```

### plan.revised
Published by: optimizer
Consumed by: core-api
Payload:
- plan_id: string
- reason: string
- changes: array of {order_id: string, field: string, old_value, new_value}

Example:
```json
{"plan_id": "plan-demo-001", "reason": "coldchain_alert", "changes": [{"order_id": "ORD-005", "field": "status", "old_value": "proposed", "new_value": "cancelled"}]}
```

### order.status
Published by: core-api
Consumed by: optimizer, genai
Payload:
- order_id: string
- plan_id: string
- old_status: string
- new_status: string
- actor: string

Example:
```json
{"order_id": "ORD-004", "plan_id": "plan-demo-001", "old_status": "proposed", "new_status": "approved", "actor": "district_officer"}
```

### custody.scanned
Published by: core-api
Consumed by: coldchain, genai
Payload:
- order_id: string
- event_type: string
- actor: string
- location: string or null
- temperature_c: number or null

Example:
```json
{"order_id": "ORD-004", "event_type": "delivered", "actor": "pharmacist_h3", "location": "H3", "temperature_c": null}
```
