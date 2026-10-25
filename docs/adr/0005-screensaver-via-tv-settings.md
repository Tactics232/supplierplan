# The screensaver is handled by the TV's settings, not by the page

The display in the staff room is a Samsung Smart TV running its built-in browser in
a normal window, opening the board via a **LAN address over plain HTTP**. After a
while of static content the TV's burn-in protection (*Auto Protection Time*) starts
its screensaver; the board is back after a key press. The request was to suppress
the screensaver during a time window (school hours) and to hide the mouse pointer,
which the TV browser draws permanently in the middle of the board.

We considered the **Screen Wake Lock API** (`navigator.wakeLock.request('screen')`),
requested by the page only inside a configurable window. We rejected it:

- **No secure context.** Wake Lock exists only on HTTPS or `localhost`. The TV opens
  `http://<LAN-IP>`, where the API is simply absent, and the TV browser has no
  switch to treat an origin as secure (unlike Chrome's
  `--unsafely-treat-insecure-origin-as-secure`).
- **Firmware, not the browser.** Even over HTTPS it is doubtful that a web lock
  would stop a protection feature the TV firmware runs; there is no way to verify
  that without shipping it.

Instead the TV is configured once:

- **Auto Protection Time → Off.** The panel is not an OLED, so burn-in from the
  static header over a ~10 h school day is not a real risk.
- **The time window is the TV's own On/Off timer** (Mon–Fri). Switching the TV off
  outside school hours protects the panel better than any screensaver.

No code, no config key. Setup steps live in the README ("Smart-TV setup").

Decisions taken with it:

- **The pointer is handled on the page** (`CURSOR_HIDE_SECONDS`, default 2,
  `0` = off): `cursor: none` from page load (otherwise it would flash on every 60 s
  reload), shown again on `mousemove`. No `hover`/`pointer` media query guard —
  touch devices have no pointer, so the class is harmless there, and a guard is
  exactly what could wrongly exclude the TV. Whether the Samsung browser honours
  `cursor: none` for its own pointer was not tested beforehand; if it does not, the
  code is inert and can be switched off with `0`.
- **If the display is ever an OLED**, revisit: keep the protection on and add a
  slight periodic pixel shift on the page instead of disabling it.
- **If the board is ever opened over HTTPS** (Cloudflare URL, installed PWA) on a
  device whose screensaver is browser-controllable, Wake Lock becomes an option
  again.

Known limitation: whether the TV returns to the browser after the On timer, or
starts on live TV / the home screen, depends on the model. In the latter case the
timer only takes care of switching off, and the browser has to be opened by hand
in the morning.
