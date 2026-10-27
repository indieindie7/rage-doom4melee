# Doom4Melee for RAGE (Steam, 9200, 32-bit Rage.exe)

Edits nine text decls inside the game's own resource files. No game data is
shipped: `edits.json` only holds the changed lines, and `install.py` applies them
to your own retail files.

## What it changes
- Melee finishers: the `damage/*/melee` decls (pistol, rifle, crossbow, plasma rifle,
  both machine guns) hit for 70; `damage/melee/stun` gets dismemberment, stun,
  knockback and a bigger ragdoll impulse. Fists hit for 70, shotgun smash for 90.
- `faction/settlers/resistance`: one relationship tweak (LIKE -> LOVE).
- Authority shotgun (`weapon/regimeshotgun`): double-barrel model, 2-shell clip,
  no auto-reload or shell-by-shell reload, no magazine upgrade, pistol animations,
  ADS spread x0.35 (retail 0.9).
- Buckshot damage (`damage/shotgun/buckshot_standard`): 8 pellets x 35
  (retail 8 x 15), bigger ragdoll. Shared by all player buckshot shotguns.

## Install (PowerShell 5.1, Python 3 required)
```powershell
py -3 install.py --dry-run            # checks every edit against your files, writes nothing
py -3 install.py                      # default Steam path
py -3 install.py "D:\Games\RAGE"      # custom game dir
py -3 install.py --restore            # undo
```
Backups are `*.doom4melee-orig` next to `base\gameresources.resources` and
`dlc\dlc3\base\gameresources.resources`. Running install again is safe.
If Steam updates/verifies the files, just run install again.

## Notes
- The dlc3 table is the main one: its rows are repointed at the patched blobs.
- Saves made with an older build of this mod that used a fake dlc4 may be broken.
- Skip intros: Steam launch option `+com_skipIntroVideo 1`.
- Edit lines are exact; install fails loudly if your files are not retail 9200.
