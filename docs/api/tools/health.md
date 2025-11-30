## Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `response_mode` | string | ❌ No | "minimal" | Response verbosity: `minimal` (status only - default), `standard` (+ remediation), `full` (+ diagnostics). See [Progressive Disclosure](../PROGRESSIVE_DISCLOSURE.md). |
| `detail_level` | string | ❌ No | - | **DEPRECATED** - Use `response_mode` instead. |
| `include_cortex` | boolean | ❌ No | true | Check Cortex AI services availability |
| `include_profile` | boolean | ❌ No | true | Validate profile configuration |
| `include_catalog` | boolean | ❌ No | false | Check catalog availability |
| `request_id` | string | ❌ No | - | Optional request ID for tracing |
