# Guardrail provider configuration

## Status
Automated guardrail providers (GraniteGuardianTool for input screening and RiskAgent for output monitoring) are configured and enforced outside this design, in agent/platform settings.

## Source of truth (operator reference)
Operators verify active guardrail settings in the **AKD Labs platform UI**: the agent page → **Runtime** tab → **Guardrails** section (Input Guardrail, Output Guardrail, Custom Risks). The saved view is read-only and is the source of truth.

This design intentionally does **not** specify:
- enabled provider categories / risk IDs
- provider enforcement actions
- logging levels
- provider execution order

## Policy-level guardrails
Policy-level rules that must hold regardless of provider configuration are specified in `guardrails_spec.md`.
