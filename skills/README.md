# User Skills Directory

This is the canonical runtime directory for skills.

## How to use

1. Copy or clone a skill directory here, e.g.:

   ```bash
   cp -r /path/to/bio-single-cell-qc ./skills/
   ```

2. Restart the backend, or use the frontend **"Rescan skills folder"** button,
   or call `POST /api/skills/import-directory`.

3. The skill is registered directly from this directory.

## Directory layout

```text
skills/
├── bio-single-cell-qc/
│   ├── SKILL.md
│   ├── scripts/
│   │   └── python/
│   │       └── main.py
│   └── requirements.txt
└── bio-single-cell-normalize/
    └── ...
```

Each subdirectory must contain a `SKILL.md` file.

## Notes

- Skills imported from git/zip/external directories are also copied into this
  directory and run from here.
- `data/skill_store/skills.json` only keeps metadata (trust, enable/disable,
  version locks); it is not a second copy of the skill source.
- Skills placed here are registered with `trusted=false` by default. Use
  `POST /api/skills/{skill_id}/trust` or the frontend **Trust** button before
  running shell/unsafe code.
