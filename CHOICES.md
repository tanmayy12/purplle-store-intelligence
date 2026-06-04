# CHOICES.md

## 1. Model Selection Decisions

### YOLO model choice
- Chosen: `yolov8n.pt`
- Implemented in: `services/cv-pipeline/app/config.py`
- Rationale:
  - `YOLOv8n` is the smallest, fastest variant of YOLOv8, suitable for near real-time CCTV processing.
  - The repository emphasizes a deployable pipeline with limited compute and Docker-based service orchestration.
- Alternatives considered:
  - `yolov8s`, `yolov8m`, `yolov8l` for higher accuracy at higher compute cost.
  - A non-YOLO detector or custom model.
- Trade-offs:
  - Accepted lower absolute detection accuracy in exchange for faster inference and easier deployment.
  - Prioritized operational throughput and maintainability over top-end computer vision accuracy.

### Tracking approach
- Chosen: ByteTrack-based multi-object tracking via Ultralytics library
- Implemented in: `services/cv-pipeline/app/pipeline.py` and `services/cv-pipeline/app/event_builder.py`
- Rationale:
  - ByteTrack provides robust tracking with minimal drift and consistent IDs, which is essential for session linking.
  - It is a proven approach for retail video applications and integrates well with the existing detection pipeline.
- Alternatives considered:
  - SORT for simpler tracking.
  - DeepSORT for appearance-based ID re-identification.
  - Transformer-based trackers.
- Trade-offs:
  - ByteTrack is more robust than SORT but still lighter than DeepSORT.
  - Chose the middle ground of stable track IDs without the higher cost of full appearance reid.

### Zone detection approach
- Chosen: polygon-based point-in-polygon zone mapping and explicit line crossing
- Implemented in: `services/cv-pipeline/app/zones.py` and `services/cv-pipeline/app/event_builder.py`
- Rationale:
  - The repository uses configurable zone polygons from `config/zones/zones.yaml`.
  - `ZoneConfig.zone_at_point()` chooses the highest priority matching polygon.
  - Entry/exit lines are defined in the same YAML config and used for line crossing rules.
- Alternatives considered:
  - Learned zone classification or semantic segmentation.
  - Grid-based spatial bucketing.
- Trade-offs:
  - Chose deterministic geometry for interpretability and ease of debugging.
  - Accepted manual configuration effort in YAML over a learned zone model.

---

## 2. Event Schema Decisions

- Chosen schema:
  - `event_id`
  - `timestamp`
  - `person_id`
  - `event_type`
  - `zone_id`
  - `metadata` payload with camera, confidence, bbox, centroid, person_type, visit_number, is_reentry, zone_type, zone_name, etc.
- Implemented in:
  - `services/cv-pipeline/app/event_schema.py`
  - `services/analytics-api/app/domain/event_normalizer.py`
  - `export_events.py`
- Rationale:
  - A consistent canonical schema supports both raw CV ingestion and analytics normalization.
  - It separates high-level event type names from internal analytics event types.
- Alternatives considered:
  - Flattened schema without nested `metadata`.
  - Different event naming conventions like `entry_event`, `exit_event`.
- Trade-offs:
  - Nested `metadata` preserves extensibility and avoids schema churn.
  - Slightly more complexity in event normalization and database persistence.

---

## 3. Sessionization Design Decisions

- Chosen design:
  - `store.entry`, `store.exit` events drive session lifecycle.
  - `re_entry` events are normalized as `store.entry` with `is_reentry`.
  - `SessionEngine` maintains active sessions keyed by `track_id`.
  - staff classification updates session `person_type` and makes staff non-counted.
- Implemented in:
  - `services/analytics-api/app/domain/session_engine.py`
  - `services/analytics-api/app/domain/event_normalizer.py`
- Rationale:
  - Use event-driven state machine to represent visitor lifecycle and retain raw event history.
  - Provide explicit session persistence and allow later POS matching.
- Alternatives considered:
  - Sessionization purely from aggregated event windows.
  - End-to-end session state in the CV pipeline rather than analytics service.
- Trade-offs:
  - Chose analytics-side sessionization to keep CV pipeline focused on event generation.
  - This requires more state management in `analytics-api`, but enables richer metrics and anomaly handling.

---

## 4. Database Design Decisions

- Chosen core schema:
  - `stores`: store metadata
  - `zones`: zone metadata and polygon definitions
  - `persons`: tracked individuals
  - `events`: raw normalized events
  - `sessions`: visit sessions
  - `zone_visits`: per-zone dwell records
  - `pos_transactions` / `pos_line_items`: ground truth transaction data
  - `anomalies`: detected issues
  - `metrics`: aggregated daily/hourly snapshots
- Implemented in:
  - `services/analytics-api/app/models/*.py`
  - `services/analytics-api/alembic/versions/001_initial_schema.py`
- Rationale:
  - The event table is append-only and preserves raw tracking data.
  - Sessions and zone visits capture higher-level analytic constructs.
  - POS tables support conversion matching and revenue analysis.
- Alternatives considered:
  - Storing events only as raw JSON without relational schema.
  - Using a NoSQL store for event data.
- Trade-offs:
  - Chose relational PostgreSQL for robust queries, indexing, and schema constraints.
  - Accepted schema complexity for stronger analytics support.

---

## 5. API Architecture Decisions

- Chosen architecture:
  - FastAPI backend exposing typed REST endpoints.
  - SQLAlchemy ORM for data access.
  - Pydantic schemas for API response validation.
- Implemented in:
  - `services/analytics-api/app/main.py`
  - `services/analytics-api/app/api/routes.py`
  - `services/analytics-api/app/schemas.py`
  - `services/analytics-api/app/database.py`
- Rationale:
  - FastAPI provides modern async-capable APIs and clear documentation.
  - ORM simplifies database interactions and reduces boilerplate.
- Alternatives considered:
  - Flask or Django REST Framework.
  - Direct SQL queries without ORM.
- Trade-offs:
  - FastAPI incurs some learning curve, but gives fast development and type safety.
  - SQLAlchemy ORM provides maintainability at the cost of some raw SQL control.

---

## 6. Kafka / Redpanda Decisions

- Chosen event bus: Redpanda
- Implemented in:
  - `docker-compose.yml`
  - `services/analytics-api/app/consumers/tracking_consumer.py`
  - `services/cv-pipeline/app/main.py`
- Rationale:
  - Redpanda is Kafka-compatible and simpler to run in Docker.
  - It supports durable event streaming for raw tracking data and decouples CV generation from analytics ingestion.
- Alternatives considered:
  - RabbitMQ, Redis Streams, direct HTTP ingestion.
  - Apache Kafka proper.
- Trade-offs:
  - Chose Kafka-compatible stream as the right balance for event reliability.
  - Redpanda simplifies setup compared to full Kafka, but still adds service complexity.

---

## 7. Dashboard Technology Decisions

- Chosen stack:
  - React 18
  - TypeScript
  - Tailwind CSS
  - Recharts
- Implemented in:
  - `services/frontend/src/App.tsx`
  - `services/frontend/src/components/Dashboard.tsx`
  - `services/frontend/src/api/client.ts`
- Rationale:
  - React + TypeScript is standard for modern dashboards and supports rapid UI composition.
  - Tailwind enables fast styling without large CSS overhead.
  - Recharts provides built-in charts for funnel, line, bar, and pie charts.
- Alternatives considered:
  - Vue or Angular.
  - D3.js direct charting.
- Trade-offs:
  - Chose easier developer productivity over custom chart complexity.
  - The dashboard is lightweight and maintainable rather than highly customized.

---

## 8. Deployment Decisions

- Chosen deployment:
  - Docker Compose multi-service stack
- Implemented in:
  - `docker-compose.yml`
- Rationale:
  - Docker Compose provides a simple local and development deployment path.
  - It groups database, event bus, seed, CV, analytics, and frontend in one orchestrated definition.
- Alternatives considered:
  - Kubernetes.
  - Managed cloud services.
- Trade-offs:
  - Docker Compose is not as production-grade as Kubernetes, but it is fast to iterate and fits HackerEarth submission requirements.
  - Accepted local orchestration complexity instead of cloud-specific deployment.

---

## 9. Alternatives Considered

- Detection:
  - Could have used larger YOLO models for improved recall.
  - Could have used a custom object detector tuned to store geometry.
- Tracking:
  - Could have used DeepSORT for appearance matching.
  - Could have used simpler SORT or Hungarian-Munkres matching.
- Zone analytics:
  - Could have used neural zone classification.
  - Could have used automated clustering from trajectories.
- Sessionization:
  - Could have used purely time-window based sessions.
  - Could have built sessions in the CV pipeline instead of analytics service.
- Back-end:
  - Could have used a non-relational event store.
  - Could have exposed GraphQL instead of REST.
- Deployment:
  - Could have used Helm/K8s.
  - Could have used cloud-managed Kafka.

---

## 10. Trade-offs Accepted

- Performance vs accuracy:
  - `yolov8n` was chosen for speed over detection accuracy.
- Simplicity vs automation:
  - Manual polygon zone definitions were chosen over learned zone models.
- Centralized analytics state:
  - `analytics-api` handles session and staff logic rather than leaving it to the CV pipeline.
- Persistence vs flexibility:
  - A relational schema was chosen over raw JSON event-only storage.
- Local deployment vs production scalability:
  - Docker Compose was chosen over Kubernetes for submission simplicity.

---

## 11. Lessons Learned

- Clear separation of concerns matters:
  - CV pipeline stays focused on tracking and event generation.
  - Analytics API handles session logic and metrics.
- Data normalization is critical:
  - Normalizing raw CV event types into internal analytics types avoids downstream ambiguity.
- Staff handling must be explicit:
  - Staff classification is best represented both as a dedicated event type and as metadata.
- Re-entry requires careful timing:
  - A cooldown window (`reentry_cooldown_sec`) prevents false session inflation.
- Config-driven zones are powerful:
  - External `config/zones/zones.yaml` allows adaptation without code changes.

---

## 12. AI-Assisted Engineering Decisions

- AI was used to inspect repository structure and identify exact implementation file references.
- AI-assisted analysis helped confirm:
  - actual model choice in `services/cv-pipeline/app/config.py`
  - event normalization rules in `services/analytics-api/app/domain/event_normalizer.py`
  - session and staff handling in `services/analytics-api/app/domain/session_engine.py`
  - deployment orchestration in `docker-compose.yml`
- AI supported documentation generation and design synthesis while human review verified final accuracy.
- The final submission content reflects real repository decisions, with AI used as an engineering productivity aid rather than an autonomous source of design.