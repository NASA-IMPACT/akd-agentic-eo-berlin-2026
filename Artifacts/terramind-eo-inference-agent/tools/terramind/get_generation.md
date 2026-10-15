# Tool: terramind.get_generation

## Purpose
Poll a previously-submitted TerraMind generation job and fetch its current status and, on success, the full result payload.

## When it should be used
- After submitting a job with `terramind.generate` when `status` is not yet `succeeded`.

## Inputs (schema)
- `job_id` (string)

## Outputs (schema)
Same stable shape as `terramind.generate` (agent checks `status`, not response shape):
- `job_id` (string)
- `status` (string; exactly one of: `queued`, `starting`, `running`, `succeeded`, `failed`)
- `retry_after_s` (number, present while not done)
- `message` (string, optional): present while not done when the service has a human-readable status message

On success (`status: succeeded`), additionally includes:
- `scene`: `item_id`, `datetime`
- `tile`: `bbox`, `tile_count`
- `seed`
- `timings`
- `outputs`: keyed by product; each contains `stats`, `cog_url`
- `input`: `cog_url`, `observed_ndvi`
- Preview images may be attached as tool-returned images (no `png_url` fields)

On failure (`status: failed`):
- `error` (string): plain-language error message (including the service’s "No job <id>" response for unknown ids)
- (no `retry_after_s`; failure is final)

## Validation / business rules inside the tool
- Expected `job_id` format is 20 lowercase hex characters (the first 20 of a UUID4 hex). The tool passes `job_id` through to the service.

## Failures / retry hints
- Tool returns `status: failed` + `error` for terminal failures.

## Notes (tool vs context boundary)
- The tool reports job status and artifacts; interpretation and report narrative remain agent-owned.
