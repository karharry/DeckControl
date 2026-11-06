# DeckControl – open, portable controller software for the Ajazz AKP03E

Works with AKP03 / AKP03E / AKP03R (both hardware revisions) and Mirabox N3 clones, on Windows, macOS and Linux.

## Run
* **Windows:** double-click `DeckControl.exe` (tray icon appears, editor opens in your browser).
* **Mac:** run `DeckControl` (build it with `./build_mac.sh`, or download the artifact from the GitHub Actions workflow in `.github/workflows`).
  First launch: right-click → Open (unsigned app); allow *Accessibility* and *Input Monitoring* in System Settings → Privacy & Security so key presses can be sent.
* **Linux:** run `./install_linux.sh` (see [Linux notes](#linux-notes)), then start *DeckControl* from the application menu.
* Everything is portable: settings, plugins, templates and images live in `DeckControl-data/` next to the program. Copy the folder to move your setup.
* Close the vendor app first – only one program can talk to the device.

## Using it
Click a key/button/knob → pick an event (Press / Long press / Release / Turn → / Turn ←) → add one or more actions (they run in order; use **Wait** between them). Pages, profiles (optionally auto-switching per application) and templates are all in the editor.

If a physical button triggers the wrong slot, use *Input mapping → Learn*.

Right-click any key, button or knob to **copy** its actions and **paste** them onto another control (optionally with its icon and colours).
A key can use an emoji or a custom image (upload one, or use the built-in Home Assistant logo button).

## Extending
* **Actions:** drop a `.py` file in `DeckControl-data/plugins/` (see `example_plugin.py`), press ↻ Plugins.
* **Templates:** drop `.json` files in `DeckControl-data/templates/` (or use *Save as template…* in the editor).

## Security & remote access
* The web UI has a **login** (username + password, PBKDF2-hashed in `DeckControl-data/auth.json`). The first time you open it from the tray icon you create the account; change it any time in ⚙ Settings.
* The tray icon's link signs you in without a password, but only from the PC itself.
* ⚙ Settings → *Listen on* lets you switch from `127.0.0.1` (this PC only) to `0.0.0.0` (reachable from your network). A password is mandatory for that; restart DeckControl to apply. Traffic is plain HTTP, so use a trusted LAN/VPN or an HTTPS reverse proxy.
* Failed logins are rate-limited; sessions use HttpOnly SameSite=Strict cookies; cross-origin requests are rejected.
* Remember: anyone who can log in can run commands on this PC (the *Run command* / *Launch* actions).

## Linux notes
`./install_linux.sh` installs to `~/.local/opt/DeckControl` (settings in `DeckControl-data/` there), adds a menu entry, and installs a udev rule (`linux/70-deckcontrol.rules`, needs `sudo`) that lets your user open the controller and send key presses. Use `--no-udev` to skip the sudo step, `--uninstall` to remove everything (add `--purge` to delete your settings too).

**Requirements:** `python3` with `venv`, PyGObject (`python3-gobject` / `python3-gi`), `libhidapi-hidraw` (`hidapi` / `libhidapi-hidraw0`), and a colour emoji font. The tray icon needs StatusNotifier/AppIndicator support: KDE has it, GNOME needs the *AppIndicator and KStatusNotifierItem* extension.

**Re-run `./install_linux.sh` after your distro upgrades Python or after a big system update.** The program uses the system's Python packages, so a new Python version breaks the old environment (the app may start without a tray icon and without working shortcuts). The installer rebuilds it.

**Troubleshooting**
* *"Waiting for device" / never connects:* the vendor app must be closed (only one program can talk to the deck). Check you have access: `ls -l /dev/hidraw*` should show `+` (an ACL for your user) on the deck's nodes. If not, the udev rule is missing or doesn't cover your model: install it again, then run `sudo udevadm trigger --subsystem-match=hidraw --action=change` or replug the deck. System updates can change the default device permissions, which is why the rule is installed explicitly.
* *Another model:* find its USB id with `lsusb`, add a line to `linux/70-deckcontrol.rules` and an entry to `KNOWN` in `deckcontrol/device.py`.
* *Keyboard shortcuts / media keys do nothing:* they are sent through `/dev/uinput` (works on Wayland). `test -w /dev/uinput && echo ok` must print `ok`.
* *Blank emoji on the keys:* the key images need a bitmap colour emoji font (`NotoColorEmoji.ttf`). The installer copies one into `~/.local/share/fonts` if it finds it. Fonts in the newer COLRv1 format render blank.
* *No tray icon:* see the requirements above, then re-run the installer. The editor still works at the address printed on start (`http://127.0.0.1:8765`).
* *Logs:* `DeckControl-data/deckcontrol.log`; run `~/.local/opt/DeckControl/DeckControl` from a terminal to see errors.

## Notes on secrets
Action settings are stored as plain text in `DeckControl-data/config.json`, including tokens you enter (for example a Home Assistant long-lived token). Don't share or commit that folder, and revoke a token if it ever leaks (it also shows in screenshots of the editor).
