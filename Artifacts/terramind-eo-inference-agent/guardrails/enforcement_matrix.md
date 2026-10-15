# Guardrail enforcement matrix

## Status
Automated guardrail provider configuration (GraniteGuardianTool input screening, RiskAgent output monitoring) is managed outside this design, in agent/platform settings.

This design therefore does **not** specify provider signals, actions, logging levels, or enforcement mappings.

## SME-validated policy enforcement (non-provider)
The following guardrail behaviors are enforced at the agent policy level (see `guardrails_spec.md`):
- Refuse malicious/harmful-intent requests (no partial help).
- Refuse operational directives, and refuse to provide verdicts for operational-decision framing.
- Mark missing-reference products as **not verified** (no verdict).
- Produce partial report with no verdicts when cloud fraction > 0.5.
- Avoid beyond-the-data claims (impact/damage/casualties/causes/forecasts).

## Open items (TBD)
- None for this matrix; provider configuration is out of scope for this artifact.
