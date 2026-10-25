# networking_events.json

Optional seed list. When the events table is empty at startup, entries here are
imported once as status `discovered`. After that, events live in the database.
Only add events confirmed on the organizer's site. Example entry:

```json
{
  "title": "Event title",
  "date": "2026-11-18",
  "time": "9:00 AM ET",
  "state": "NJ",
  "location": "City, ST",
  "format": "in_person",
  "organizer": "Host organization",
  "target_groups": ["B2B_Networking", "Small_Business"],
  "registration_url": "https://..."
}
```

`format` is `in_person`, `virtual` or `hybrid`. `state` must be one of NY, NJ, CT, MA, PA, DE, DC.
