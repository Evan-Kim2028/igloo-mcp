# Authentication Options

Igloo MCP uses Snowflake CLI profiles for authentication. We recommend SSO (Okta) via the external browser for most users, with password as a fallback and key‑pair for advanced/headless automation.

## Recommended: SSO (Okta) via external browser

```bash
snow connection add \
  --connection-name my-profile \
  --account <account>.<region> \
  --user <username> \
  --authenticator externalbrowser \
  --warehouse <warehouse>

# If your org requires an explicit Okta URL
# --authenticator https://<your_okta_domain>.okta.com
```

## Fallback: Password (no SSO)

```bash
snow connection add \
  --connection-name my-profile \
  --account <account>.<region> \
  --user <username> \
  --password \
  --warehouse <warehouse>
```

## Advanced: RSA Key‑Pair (headless/automation)

```bash
mkdir -p ~/.snowflake
openssl genrsa -out ~/.snowflake/key.pem 2048
openssl rsa -in ~/.snowflake/key.pem -pubout -out ~/.snowflake/key.pub
chmod 400 ~/.snowflake/key.pem

# Upload public key to Snowflake (strip header/footer)
cat ~/.snowflake/key.pub | grep -v "BEGIN\|END" | tr -d '\n'
-- In Snowflake:
ALTER USER <username> SET RSA_PUBLIC_KEY='<paste_here>';

snow connection add \
  --connection-name my-profile \
  --account <account>.<region> \
  --user <username> \
  --private-key-file ~/.snowflake/key.pem \
  --warehouse <warehouse>
```

## Troubleshooting SSO/Okta

- Verify the profile uses SSO: run `health_check` and check the `authentication` section
  - `authenticator: externalbrowser` → Okta/SAML via browser
  - `authenticator: https://<okta-domain>` → direct Okta URL
- Browser didn’t open
  - Ensure a default browser is available (corporate devices/VPN may block)
  - Try `snow sql -q "SELECT 1" --connection <profile>` to prompt SSO outside igloo-mcp
- Account identifier mismatch
  - Must match Snowflake URL region: `<acct>.<region>` (e.g., `abc12345.us-east-1`)
- VPN/IdP policies
  - Connect VPN before triggering SSO if required by your org

## Inspecting Active Authenticator

Use `health_check` (via MCP) to surface the active profile and authenticator:

```json
{
  "profile": {
    "status": "valid",
    "profile": "my-profile",
    "authentication": {
      "authenticator": "externalbrowser",
      "is_externalbrowser": true,
      "is_okta_url": false
    }
  }
}
```

If it's not `externalbrowser` or an Okta URL and you expect SSO, update the profile with `--authenticator` as shown above.

## See Also

- [Installation Guide](installation.md) - Complete installation and profile setup
- [Getting Started Guide](getting-started.md) - Quick start overview
- [Configuration Guide](configuration.md) - Advanced configuration options
- [MCP Integration Guide](mcp-integration.md) - MCP client setup
