# networking_events.json

Curated, manually verified events used by the `search_multistate_networking_events` MCP tool.
Only add events confirmed on the organizer's site. Example entry:

```json
{
  "event_id": "evt_example",
  "title": "Event title",
  "date": "2026-11-18",
  "time": "9:00 AM ET",
  "state": "NJ",
  "location": "City, ST",
  "format": "in_person",
  "organizer": "Host organization",
  "target_groups": ["MWBE", "Supplier_Diversity"],
  "registration_url": "https://..."
}
```

`format` is `in_person`, `virtual` or `hybrid`. `state` must be one of NY, NJ, CT, MA, PA, DE, DC.
