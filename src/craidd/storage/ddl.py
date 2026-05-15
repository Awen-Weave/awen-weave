"""
src/craidd/storage/ddl.py — the v0.1 DuckDB schema, as DDL.

A faithful transcription of design/v0.1-schema.md §11, split across the
two database files the §2 topology defines:

  CRAIDD_DDL  -> craidd.duckdb : entity, predicate, claim, the three
                 claim indexes, and the current_claim and cy_coverage
                 views.
  PRAWF_DDL   -> prawf.duckdb  : the append-only prawf_log table only.

The split is deliberate (§2): a corruption in one database cannot reach
the other. The schema layer (src/craidd/schema/) mirrors the vocabularies
encoded in the CHECK constraints here — when one changes the other must
change in the same commit (architecture.md §4 boundary 4).

Note: the claim.value_geom column uses the GEOMETRY type, which DuckDB
provides via its `spatial` extension — see connect_craidd() in
database.py, which loads it.
"""
from __future__ import annotations


# --- craidd.duckdb -----------------------------------------------------------
CRAIDD_DDL = """
-- Dolgellau Town Dataset — craidd.duckdb schema (v0.1).
-- Source of truth: design/v0.1-schema.md §11.

CREATE TABLE entity (
  entity_id     VARCHAR PRIMARY KEY,
  entity_type   VARCHAR NOT NULL CHECK (entity_type IN
                ('building','street','area','town','tenancy','event',
                 'research_question','source','person')),
  uprn          BIGINT,
  toid          VARCHAR,
  visibility    VARCHAR CHECK (visibility IN ('public','restricted','private')
                               OR visibility IS NULL),
  created_at    TIMESTAMP NOT NULL DEFAULT NOW(),
  notes         TEXT
);

CREATE TABLE predicate (
  name                    VARCHAR PRIMARY KEY,
  value_type              VARCHAR NOT NULL CHECK (value_type IN
                          ('text','int','real','date','geom','bilingual','entity_ref')),
  cardinality             VARCHAR NOT NULL CHECK (cardinality IN ('single','multi')),
  applies_to_types        VARCHAR NOT NULL,
  description_cy          VARCHAR NOT NULL,
  description_en          VARCHAR NOT NULL,
  constraint_json         VARCHAR,
  required_qualifiers     VARCHAR,
  added_at                TIMESTAMP NOT NULL DEFAULT NOW(),
  added_by                VARCHAR NOT NULL,
  deprecated_at           TIMESTAMP,
  deprecated_by           VARCHAR,
  deprecation_reason      VARCHAR,
  superseded_by_predicate VARCHAR REFERENCES predicate(name)
);

CREATE TABLE claim (
  claim_id          VARCHAR PRIMARY KEY,
  subject_id        VARCHAR NOT NULL REFERENCES entity(entity_id),
  predicate         VARCHAR NOT NULL REFERENCES predicate(name),
  value_text        VARCHAR,
  value_int         BIGINT,
  value_real        DOUBLE,
  value_date        DATE,
  value_date_text   VARCHAR,
  value_geom        GEOMETRY,
  value_cy          VARCHAR,
  value_en          VARCHAR,
  value_entity_ref  VARCHAR REFERENCES entity(entity_id),
  qualifiers_json   VARCHAR,
  source_id         VARCHAR NOT NULL REFERENCES entity(entity_id),
  recorded_by       VARCHAR NOT NULL,
  recorded_at       TIMESTAMP NOT NULL DEFAULT NOW(),
  confidence        VARCHAR NOT NULL CHECK (confidence IN ('high','medium','low')),
  evidence_uri      VARCHAR,
  superseded_by     VARCHAR REFERENCES claim(claim_id),
  status            VARCHAR NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active','superseded','disputed','withdrawn'))
);

CREATE INDEX claim_subject_predicate_idx ON claim(subject_id, predicate);
CREATE INDEX claim_status_idx ON claim(status);
CREATE INDEX claim_value_entity_ref_idx ON claim(value_entity_ref);

CREATE VIEW current_claim AS
  SELECT * FROM claim
  WHERE status IN ('active','disputed')
  AND superseded_by IS NULL;

CREATE VIEW cy_coverage AS
  SELECT
    p.name AS predicate,
    COUNT(*) FILTER (WHERE c.value_cy IS NOT NULL) AS cy_populated,
    COUNT(*) AS total,
    100.0 * COUNT(*) FILTER (WHERE c.value_cy IS NOT NULL)
      / NULLIF(COUNT(*), 0) AS pct
  FROM claim c
  JOIN predicate p ON p.name = c.predicate
  WHERE p.value_type = 'bilingual'
  AND c.status = 'active'
  GROUP BY p.name;
"""


# --- prawf.duckdb ------------------------------------------------------------
PRAWF_DDL = """
-- Dolgellau Town Dataset — prawf.duckdb schema (v0.1).
-- The append-only, hash-chained Prawf log. A separate database file from
-- craidd.duckdb so a corruption in one cannot reach the other.
-- Source of truth: design/v0.1-schema.md §11.

CREATE TABLE prawf_log (
  log_id         VARCHAR PRIMARY KEY,
  ts             TIMESTAMP NOT NULL DEFAULT NOW(),
  actor          VARCHAR NOT NULL,
  action         VARCHAR NOT NULL,
  target_id      VARCHAR NOT NULL,
  payload_json   VARCHAR NOT NULL,
  prev_hash      VARCHAR,
  this_hash      VARCHAR NOT NULL
);
"""
