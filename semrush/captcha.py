"""reCAPTCHA Enterprise v3 tokens for Semrush's free-tools API.

Every POST /free-tools/api/v2/<tool>/ carries `recaptcha_v3`, a token the
page mints with grecaptcha.enterprise.execute() (site key
config-independent: 6LcwzpErAAAAALabrs4m1pOnRKkikqUUsc3jQ49j, loaded with
render=explicit so the widget id is 0). No solver service is involved —
v3 is invisible, so a real browser on the real page mints a valid token
in ~1 s; Semrush then scores it server-side and answers 400 "Invalid
reCAPTCHA token" only for forged / expired ones.

Measured 2026-09-25 (headed patchright, direct egress): the page is ready
~8 s after load, then execute(0, {action}) answers in 1-2 s, tokens mint
back-to-back, one token is accepted by ANY tool (they share the site key),
and a token minted on the direct egress is accepted for a POST sent through
a residential proxy exit — the per-tool daily quota is keyed on the POSTing
IP, so semrush/keywords.py rotates exits per call while the browser stays
put. execute(SITE_KEY, …) (the documented v3 form) never resolves on this
page; execute(0, …) (the explicit widget) does.

Shape: ONE shared headed Chrome (the crunchbase identity-browser pattern —
launched on first demand, every playwright call on its owner thread via
driver.call(), closed by a reaper after config.SEMRUSH_BROWSER_IDLE seconds
without a mint, relaunched on the next). Mints are serialized.
"""
import threading
import time

import config

SITE = "https://www.semrush.com"
MINT_PAGE = SITE + "/analytics/keywordoverview/"
PAGE_SETTLE = 6            # seconds after domcontentloaded before the first execute
READY_POLL = 1.0
READY_TIMEOUT = 40         # seconds for grecaptcha.enterprise + its client to appear

_READY_JS = """() => !!(window.grecaptcha && grecaptcha.enterprise && window.___grecaptcha_cfg
                        && Object.keys(window.___grecaptcha_cfg.clients || {}).length)"""

_EXECUTE_JS = """(timeoutMs) => new Promise((res) => {
  const t = setTimeout(() => res({error: 'timeout'}), timeoutMs);
  try {
    grecaptcha.enterprise.execute(0, {action: 'submit'}).then(
      tok => { clearTimeout(t); res({token: tok}); },
      err => { clearTimeout(t); res({error: String(err)}); });
  } catch (e) { clearTimeout(t); res({error: 'throw ' + String(e)}); }
})"""


class CaptchaError(Exception):
    """The browser could not mint a token (page wedged, grecaptcha missing)."""


class _Browser:
    def __init__(self):
        self.lock = threading.RLock()
        self.driver = None
        self.ua = None
        self.last_used = 0.0
        self._reaper = None

    # ---- lifecycle ------------------------------------------------------------
    def _launch(self):
        from chrome_manager import create_scope
        from patchright_driver import PatchrightDriver
        self._close_locked()
        proxy = config.semrush_mint_proxy()
        print(f"semrush: launching the captcha browser "
              f"(egress={'direct' if not proxy else proxy.rsplit('@', 1)[-1]})", flush=True)
        with create_scope():
            self.driver = PatchrightDriver(proxy_url=proxy, headless=False)
        try:
            self.driver.goto(MINT_PAGE, referer="https://www.google.com/")
            time.sleep(PAGE_SETTLE)
            self._wait_ready()
            self.ua = self.driver.evaluate("navigator.userAgent")
        except Exception:
            self._close_locked()
            raise
        if self._reaper is None:
            self._reaper = threading.Thread(target=self._reap, name="semrush-captcha-reaper", daemon=True)
            self._reaper.start()

    def _wait_ready(self):
        deadline = time.monotonic() + READY_TIMEOUT
        while time.monotonic() < deadline:
            try:
                if self.driver.evaluate(_READY_JS, main_world=True):
                    return
            except Exception:
                pass
            time.sleep(READY_POLL)
        raise CaptchaError("grecaptcha did not load on the free-tools page")

    def _close_locked(self):
        driver, self.driver = self.driver, None
        if driver is not None:
            try:
                driver.close()
            except Exception:
                pass

    def close(self):
        with self.lock:
            self._close_locked()

    def _reap(self):
        while True:
            time.sleep(30)
            with self.lock:
                if self.driver is not None and time.time() - self.last_used > config.SEMRUSH_BROWSER_IDLE:
                    print("semrush: closing the idle captcha browser", flush=True)
                    self._close_locked()

    # ---- minting --------------------------------------------------------------
    def mint(self):
        """-> (token, user_agent). Relaunches the browser once when the page
        is wedged or the token call fails."""
        with self.lock:
            for attempt in range(2):
                if self.driver is None:
                    try:
                        self._launch()
                    except Exception as e:
                        # goto TargetClosedError / startup timeout while an old Chrome dies
                        print(f"semrush: captcha browser launch failed ({type(e).__name__}: {e}); "
                              f"{'relaunching' if attempt == 0 else 'giving up'}", flush=True)
                        continue
                self.last_used = time.time()
                try:
                    res = self.driver.evaluate(_EXECUTE_JS, config.SEMRUSH_MINT_TIMEOUT * 1000, main_world=True)
                except Exception as e:
                    res = {"error": f"evaluate failed: {type(e).__name__}: {e}"}
                token = (res or {}).get("token") if isinstance(res, dict) else None
                if token:
                    return token, self.ua
                print(f"semrush: captcha mint failed ({(res or {}).get('error')}); "
                      f"{'relaunching' if attempt == 0 else 'giving up'}", flush=True)
                self._close_locked()
            raise CaptchaError("could not mint a reCAPTCHA token")


_browser = _Browser()


def token():
    """A fresh reCAPTCHA Enterprise token and the minting browser's user-agent."""
    return _browser.mint()


def close():
    _browser.close()


def status():
    with _browser.lock:
        return {"browser": _browser.driver is not None, "last_used": _browser.last_used}


if __name__ == "__main__":
    # Smoke test: python semrush/captcha.py
    t0 = time.time()
    tok, ua = token()
    print(f"token {tok[:32]}… ({len(tok)} chars) in {time.time() - t0:.1f}s; ua={ua}")
    t0 = time.time()
    tok2, _ = token()
    print(f"second token in {time.time() - t0:.1f}s; distinct={tok2 != tok}")
    close()
