# Risk Signal Policy (Stage 4F)

RISK_SIGNAL = traceable observation: risk_type, description, supporting
evidence, source document/location, requires_management_review=true.
Generated ONLY from validated inputs (gaps, ambiguities, conflicts,
missing bid security). NEVER severity, probability, monetary/business impact,
or BID/NO-BID — absent fields stay absent, not defaulted. Anything interpretive
beyond grounding stays NOT_CONFIGURED. Tests assert the bans on every sample.
