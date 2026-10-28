# Cookbook: send the weekly cash report through Microsoft Graph (one-time setup)

Goal: the Databricks job sends the weekly cash report from one shared mailbox, through Microsoft Graph `sendMail`,
with an app that can send as that mailbox and no other. Needs a Microsoft 365 / Exchange admin.
Design: `openspec/changes/weekly-cash-report/design.md`.

Why Graph and not SMTP: SMTP AUTH needs a mailbox password in a secret and Microsoft is phasing out basic
authentication for it. Graph uses the app's own credentials, the same way the SharePoint reader does.

| Item | Value |
|---|---|
| Sender | `noreply@<your domain>` (`MAIL_SENDER`); replies go to `finance-reports@<your domain>` (`MAIL_REPLY_TO`). Both are shared mailboxes |
| Entra app | `bank-etl-mailer`, single tenant, no redirect URI. Separate from the read-only SharePoint app |
| Permission | Microsoft Graph, **Application**, `Mail.Send`, admin consent |
| Limit | Exchange application access policy: this app may act only on the sender mailbox |

## 1. The sender mailbox
Use the existing shared mailbox, or create one: Exchange admin center (https://admin.exchange.microsoft.com) ->
Recipients -> Mailboxes -> **Add a shared mailbox** -> name `ConceptLabs Finance Reports`, address `finance-reports@...`.
A shared mailbox needs no licence. Note the full address: it is `MAIL_SENDER`.

## 2. Create the mailer app
1. https://entra.microsoft.com -> Entra ID -> App registrations -> **New registration**.
2. Name `bank-etl-mailer`; *Single tenant*; no redirect URI; **Register**.
3. Copy **Application (client) ID** -> `MAIL_CLIENT_ID`. (The tenant id is the same as `SP_TENANT_ID`.)
4. Certificates & secrets -> **New client secret** (12 or 24 months) -> copy the **Value** -> `MAIL_CLIENT_SECRET`. Set a calendar reminder 30 days before expiry.

## 3. Add the permission
API permissions -> Add a permission -> Microsoft Graph -> **Application permissions** -> `Mail.Send` -> Add ->
**Grant admin consent**. Status shows a green tick.

**Important:** on its own, `Mail.Send` (application) lets the app send as **any mailbox in the tenant**. Do step 4 before using it.

## 4. Limit the app to the sender mailboxes (Exchange Online PowerShell, admin)
No Exchange admin page exists for this; it is PowerShell only. Azure Cloud Shell (https://shell.azure.com, choose PowerShell)
works without installing anything, or `brew install --cask powershell` then `pwsh` on a Mac.
```powershell
Install-Module ExchangeOnlineManagement -Scope CurrentUser   # skip in Cloud Shell
Connect-ExchangeOnline

# a security group that holds only the mailboxes the app may send as
New-DistributionGroup -Name "bank-etl-mailer-scope" -Type Security -Members finance-reports@<domain>,noreply@<domain>
Get-DistributionGroup bank-etl-mailer-scope | Format-List PrimarySmtpAddress     # note the address
```
The group's address uses the default domain, e.g. `bank-etl-mailer-scope@<tenant>.onmicrosoft.com`, not your own domain.
Use that exact address below; `@<your domain>` fails with "identity of the policy scope could not be resolved".
```powershell
New-ApplicationAccessPolicy -AppId <MAIL_CLIENT_ID> -PolicyScopeGroupId bank-etl-mailer-scope@<tenant>.onmicrosoft.com `
  -AccessRight RestrictAccess -Description "bank-etl-mailer may act only on the finance-reports and noreply mailboxes"
```
Before the policy exists, `Get-ApplicationAccessPolicy` answers "couldn't be found": that means none is set, and `Mail.Send` lets the app send as any mailbox.
Microsoft is moving to "RBAC for Applications" in Exchange Online for the same scoping; the policy above still works.

## 5. Check the limit (allow up to an hour for it to apply)
```powershell
Test-ApplicationAccessPolicy -Identity finance-reports@<domain> -AppId <MAIL_CLIENT_ID>   # Granted
Test-ApplicationAccessPolicy -Identity noreply@<domain> -AppId <MAIL_CLIENT_ID>            # Granted
Test-ApplicationAccessPolicy -Identity <a personal mailbox> -AppId <MAIL_CLIENT_ID>        # Denied
```
From the repo: `python scripts/graph_mail_check.py` sends one plain test mail to `MAIL_DRY_RUN_TO` (HTTP 202);
`python scripts/graph_mail_check.py --as <a personal mailbox>` must answer HTTP 403 once the policy is active.

## 6. Fill `.env` (gitignored; never paste secrets in chat or git)
```
MAIL_CLIENT_ID=<Application (client) ID>
MAIL_CLIENT_SECRET=<secret Value>
MAIL_SENDER=noreply@<domain>
MAIL_REPLY_TO=finance-reports@<domain>
MAIL_RECIPIENTS=first@example.com|First Person,second@example.com|Second Person
MAIL_DRY_RUN_TO=<your own address>
MAIL_MODE=dry
```
`MAIL_RECIPIENTS`: comma-separated `address|Display Name`; no commas inside a name. Keep `MAIL_MODE=dry` until the first dry run looks right.

## 7. Test (bolt M0)
`scripts/graph_mail_check.py` sends one plain test mail to `MAIL_DRY_RUN_TO` from the sender mailbox, locally and
from a serverless job. Expected: HTTP 202 and the mail arrives from the shared mailbox.

## Troubleshooting
| Symptom | Cause / fix |
|---|---|
| `AADSTS7000215` invalid client secret | Copied the Secret ID, or it expired. Make a new secret |
| 403 `ErrorAccessDenied` on sendMail | Application access policy not applied yet (wait), or the mailbox is not in the scope group |
| 403 `Authorization_RequestDenied` | `Mail.Send` not consented, or Delegated chosen instead of Application |
| 404 `MailboxNotEnabledForRESTAPI` / `ResourceNotFound` | Wrong sender address, or the mailbox is not hosted in Exchange Online |
| Mail lands in spam | Send a dry run to yourself first and mark not spam; the shared mailbox uses your domain's SPF and DKIM |
| Attachment rejected | Over about 3 MB in this call; the report PDFs are far smaller |

## Later additions
- Sender decision (2026-10-24): sending as `finance-reports` returned 403 from Graph for a while although `Test-ApplicationAccessPolicy` said Granted. `noreply` worked, so it is the sender and `finance-reports` is the Reply-To.
- `conceptlabs.com` has SPF but no DKIM or DMARC. Turn on DKIM (Defender portal, Email authentication settings, DKIM; two CNAMEs at the DNS host) and add `v=DMARC1; p=none` to help Gmail trust the mail.
- Run the real report to the dry-run address with `python scripts/send_test_report.py <sunday>`; the scheduled job is `bank-etl-weekly-cash-report` (see the runbook page).
