# tripmine ⛏️🗺️

**Mine trips from your photo archives.**

You have thousands of photos in Google Photos, Apple iCloud, or a hard drive — and no idea what's actually in them. `tripmine` turns a photo export into a **relive-able map and day-by-day timeline** of everywhere you've been.

Built while mining a real **2019 Iceland road trip** (~1,000 photos) — this project is dogfooded on real data from day one.

## The problem

- 📸 10,000+ photos, scattered across Google Photos and iCloud
- 🧠 You remember the *highlights* — not the route, not the order, not the stops
- 💸 Paid services want subscriptions to do basic EXIF→map work

## What tripmine does

1. **Extract** — unpack a Google Takeout export (iCloud coming) into photos + metadata
2. **Track** — read EXIF date/time/GPS → reverse-geocode to place names (free, no API keys) → cluster into stops
3. **Map** — output an interactive map + timeline: every stop, photo counts, time spent, day by day

## Quick start

```bash
pip install tripmine          # not on PyPI yet — coming after v0.1

# Unpack your Google Takeout zip
tripmine extract ~/Downloads/takeout-20260817.zip -o ~/photos

# Build the tracker
tripmine track ~/photos -o tracker/
# → tracker/timeline.json + tracker/map.html
```

## Roadmap

- [x] Project scaffold (this repo)
- [ ] `extract` — Takeout zip → normalized photos + JSON metadata
- [ ] `track` — EXIF → places → stops → timeline + interactive map
- [ ] iCloud export support
- [ ] Story suggestions (which stops deserve a video)
- [ ] Video script generation for your travel channel

## Why free / no API keys

- EXIF parsing: local
- Reverse geocoding: OpenStreetMap Nominatim (free, generous limits)
- Maps: self-contained HTML with OpenStreetMap tiles

## License

MIT © 2026 Azim Shaik
