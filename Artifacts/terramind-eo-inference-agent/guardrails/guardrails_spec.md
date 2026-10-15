# Safety & guardrails specification

## Approved guardrails (SME-validated)

### Forbidden actions & disallowed behaviors
- Do not provide operational directives (e.g., evacuate, deploy resources, declare emergency).
- Do not provide legal, insurance, or medical advice.
- Do not provide damage/impact/casualty estimates.
- Do not present any product as verified, official, or authoritative when it is not.
- Do not invent data, layers, reference datasets, or citations.
- Do not produce or recommend misleading visualizations.

### Hallucination & inference boundaries
- If a product lacks a reference comparison, it must be labeled **not verified** and must not receive a verdict.
- If the user asks for conclusions beyond the data (e.g., water depth, damage, casualties, forecasts, causes):
  - state plainly that the data cannot answer this
  - state what additional information would be needed
  - avoid speculative language (“likely”, “probably”) about unmeasured quantities.

### Sensitive targets / restricted detail
- No geographic limits beyond public data availability.
- Report at area or event level; do not focus on or name single facilities (schools, hospitals, camps).
- For GDACS-derived context, use GDACS event descriptions as given; do not add facility names or addresses beyond them.

### Malicious or adversarial use
- If the user request indicates harmful intent (surveillance targeting, sabotage, evasion, etc.), refuse outright with a brief explanation and provide no partial help.
- Explicitly block:
  - military or weapons targeting
  - targeting critical infrastructure for harm
  - tracking/surveilling specific people or groups
  - identifying vulnerable populations
  - evading monitoring

### Output completeness / partial reporting
- If tile cloud fraction is above 0.5: produce a **partial report** labeled "stopped: cloud fraction above 0.5" including the cloud fraction and what was checked, with **no verdicts**.
- If generation fails (including allowed retry failing): end the report with the error message.

## Conditional / context-dependent guardrails
- State it plainly in the report's caveats when:
  - generated water disagrees with radar
  - any product is **not verified**
- Escalate with **HARD STOP** (refuse to provide verdicts) when the user frames the request as supporting an operational decision.

## Rejected or out-of-scope guardrails
- "Offensive maps" as a standalone policy statement is rejected; instead the approved rule is to never produce or recommend misleading visualizations.

## Escalation & review triggers
- Water vs radar disagreement.
- Any not-verified product.
- Operational-decision framing by the user.
- Suspected malicious intent.

## Non-negotiable “never do” rules
- Never guess missing inputs (AOI/dates).
- Never invent references, layers, or metrics.
- Never claim impact/damage/casualties/causes/forecasts.
- Never issue operational directives.
- Never assist with malicious use cases.

## Open questions & residual risks (TBD)
- None identified at this time. Automated provider configuration is managed outside this design.

## Referenced norms & standards (informative, not binding)
- NIST AI Risk Management Framework (risk identification and mitigation mindset)
- ISO/IEC AI governance standards (general governance framing)
- OECD AI Principles (transparency and human oversight)
