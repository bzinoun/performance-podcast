# HEARTBEAT.md

```markdown
# Heartbeat check every 30 minutes
# Tasks:
# 1. Verify gateway is running
# 2. Check for missed cron jobs and re-execute if needed
```

```json
{
  "gatewayCheck": {
    "enabled": true,
    "intervalMinutes": 30
  },
  "missedCronCatchup": {
    "enabled": true,
    "jobs": ["Veille Tech & AI - Badr", "Sport Reminder - Badr"]
  }
}
```
