# Known faces (reference photos)

Put clear, front-facing photos here. **Everything in this folder except this
README and the `.gitkeep` files is git-ignored** — reference photos are
personal biometric data and must not be committed or shared. Only enrol people
who have agreed to it.

```
authorized/            people who ARE allowed in the area (no alert when seen)
    alice.jpg              -> identity "alice"
    bob/1.jpg  bob/2.jpg   -> identity "bob" (2-3 photos per person is best)
watchlist/             people who should raise a CRITICAL alert when seen
    suspect_01/1.jpg
```

Tips: one face per photo works best (the largest face is used), good lighting,
face at least ~150 px wide, no sunglasses/mask. After adding photos, restart
the AI worker — the gallery is loaded at start-up.

An "unrecognized person" alert is only raised when the `authorized/` folder
contains at least one person; with an empty gallery, unknown faces are just
labelled and never alerted.
