# DeckControl – open, portable controller software for the Ajazz AKP03E

Works with AKP03 / AKP03E / AKP03R (both hardware revisions) and Mirabox N3 clones.

## Run
* **Windows:** double-click `DeckControl.exe` (tray icon appears, editor opens in your browser).
* **Mac:** run `DeckControl` (build it with `./build_mac.sh`, or download the artifact from the GitHub Actions workflow in `.github/workflows`).
  First launch: right-click → Open (unsigned app); allow *Accessibility* and *Input Monitoring* in System Settings → Privacy & Security so key presses can be sent.
* Everything is portable: settings, plugins, templates and images live in `DeckControl-data/` next to the program. Copy the folder to move your setup.
* Close the vendor app first – only one program can talk to the device.

## Using it
Click a key/button/knob → pick an event (Press / Long press / Release / Turn → / Turn ←) → add one or more actions (they run in order; use **Wait** between them). Pages, profiles (optionally auto-switching per application) and templates are all in the editor.

If a physical button triggers the wrong slot, use *Input mapping → Learn*.

## Extending
* **Actions:** drop a `.py` file in `DeckControl-data/plugins/` (see `example_plugin.py`), press ↻ Plugins.
* **Templates:** drop `.json` files in `DeckControl-data/templates/` (or use *Save as template…* in the editor).

## Security & remote access
* The web UI has a **login** (username + password, PBKDF2-hashed in `DeckControl-data/auth.json`). The first time you open it from the tray icon you create the account; change it any time in ⚙ Settings.
* The tray icon's link signs you in without a password, but only from the PC itself.
* ⚙ Settings → *Listen on* lets you switch from `127.0.0.1` (this PC only) to `0.0.0.0` (reachable from your network). A password is mandatory for that; restart DeckControl to apply. Traffic is plain HTTP, so use a trusted LAN/VPN or an HTTPS reverse proxy.
* Failed logins are rate-limited; sessions use HttpOnly SameSite=Strict cookies; cross-origin requests are rejected.
* Remember: anyone who can log in can run commands on this PC (the *Run command* / *Launch* actions).
