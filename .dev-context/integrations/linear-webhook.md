# Linear + n8n Webhook Integration

> Stub configuration for syncing Linear issues with project STATUS.md

## Project Identifier

- **Project ID**: `__PROJECT_ID__` (from `.dev-context/project.conf`)
- **Linear team**: `__LINEAR_TEAM__`
- **Issue format**: `__PROJECT_ID__-001`, `__PROJECT_ID__-002`, ...
- **Branch format**: `feat/__PROJECT_ID__-42-short-desc`

## Linear Project Setup

1. Create a new Linear project with identifier `__PROJECT_ID__`
2. Set the team to `__LINEAR_TEAM__` (or create a new team)
3. Issues will be auto-numbered as `__PROJECT_ID__-XXX`

## n8n Workflow Overview

```
Linear Webhook → n8n → Parse Issue → Update STATUS.md (via git commit)
```

## Webhook Configuration

```yaml
# n8n webhook node config
webhook:
  method: POST
  path: /linear-webhook-__PROJECT_ID__
  authentication: headerAuth
  header_name: X-Linear-Signature
  # Set the secret in n8n credentials, matching Linear's webhook secret

# Linear webhook settings (linear.app → Settings → API → Webhooks)
linear:
  url: https://<your-n8n-domain>/webhook/linear-webhook-__PROJECT_ID__
  events:
    - issueCreate
    - issueUpdate
    - issueRemove
  team_filter: __LINEAR_TEAM__
  # Only process issues matching this project identifier
  issue_prefix: __PROJECT_ID__
```

## Payload Mapping

| Linear Field            | STATUS.md Field     | Example                     |
|------------------------|---------------------|-----------------------------|
| `issue.identifier`     | Active task prefix  | `__PROJECT_ID__-42`         |
| `issue.title`          | Active task         | "Add user auth"             |
| `issue.state.name`     | Phase               | "In Progress"               |
| `issue.assignee`       | (filter condition)  |                             |
| `issue.labels`         | (used for routing)  |                             |

## Setup Steps

1. In Linear: Create project with team key `__PROJECT_ID__`
2. In n8n: Create new workflow with Webhook trigger node
3. In Linear: Settings → API → Webhooks → New webhook
4. Set the webhook URL to `https://<your-n8n-domain>/webhook/linear-webhook-__PROJECT_ID__`
5. Add a Function node in n8n to format the STATUS.md update
6. Add a Git node (or shell exec) to commit the change
7. Test with a sample issue: create `__PROJECT_ID__-1` and verify STATUS.md updates

## Security Notes

- Verify `X-Linear-Signature` header using HMAC-SHA256
- Restrict webhook to your Linear workspace IP range if possible
- Store webhook secret in n8n credentials, not in code
