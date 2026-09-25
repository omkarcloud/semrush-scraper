"""A small headed Chrome (patchright, the undetected Playwright fork) that
the captcha module uses to mint reCAPTCHA tokens on Semrush's free-tool
page.

Playwright's sync API is bound to the thread that created it, so every
driver owns one daemon thread that launches the browser and runs every
page operation; the public methods hand callables to that thread and wait.

Real Google Chrome is used when installed (channel="chrome"); otherwise
patchright's bundled Chromium (`python -m patchright install chromium`).
On Linux without a display (Docker, servers) a virtual X display is
started once with pyvirtualdisplay, because the browser runs headed.
"""
import os
import queue
import shutil
import sys
import tempfile
import threading

STARTUP_TIMEOUT = 120
CALL_TIMEOUT = 90
GOTO_TIMEOUT_MS = 60000

_display = None
_display_lock = threading.Lock()


def _ensure_display():
    global _display
    if not sys.platform.startswith("linux") or os.environ.get("DISPLAY"):
        return
    with _display_lock:
        if _display is None:
            from pyvirtualdisplay import Display
            _display = Display(visible=False, size=(1920, 1080))
            _display.start()


class PatchrightDriver:
    def __init__(self, proxy_url=None, headless=False):
        # proxy_url is accepted for interface parity and ignored: the captcha
        # browser always runs on your own connection (config.semrush_mint_proxy)
        self._headless = bool(headless)
        if not self._headless:
            _ensure_display()
        self._jobs = queue.Queue()
        self._started = threading.Event()
        self._start_error = None
        self._profile_dir = tempfile.mkdtemp(prefix="semrush-chrome-")
        self._thread = threading.Thread(target=self._main, args=(),
                                        daemon=True, name="semrush-chrome")
        self._thread.start()
        if not self._started.wait(STARTUP_TIMEOUT):
            raise RuntimeError(f"browser startup timed out after {STARTUP_TIMEOUT}s")
        if self._start_error is not None:
            raise RuntimeError(f"browser startup failed: {self._start_error}")

    def _launch(self, pw):
        kwargs = dict(user_data_dir=self._profile_dir, headless=self._headless, no_viewport=True)
        try:
            return pw.chromium.launch_persistent_context(channel="chrome", **kwargs)
        except Exception:
            # no Google Chrome on this machine: patchright's bundled Chromium
            return pw.chromium.launch_persistent_context(**kwargs)

    def _main(self):
        from patchright.sync_api import sync_playwright
        pw = context = None
        try:
            pw = sync_playwright().start()
            context = self._launch(pw)
            page = context.pages[0] if context.pages else context.new_page()
        except Exception as e:
            self._start_error = e
            self._started.set()
            for closer in (context, pw):
                try:
                    if closer is not None:
                        closer.close() if closer is context else closer.stop()
                except Exception:
                    pass
            return
        self._started.set()
        while True:
            job = self._jobs.get()
            if job is None:
                break
            fn, box, done = job
            try:
                box["result"] = fn(page)
            except Exception as e:
                box["error"] = e
            done.set()
        for closer in (context.close, pw.stop):
            try:
                closer()
            except Exception:
                pass

    def call(self, fn, timeout=CALL_TIMEOUT):
        """Run fn(page) on the browser thread and return its result."""
        box, done = {}, threading.Event()
        self._jobs.put((fn, box, done))
        if not done.wait(timeout):
            raise RuntimeError(f"browser operation timed out after {timeout}s")
        if "error" in box:
            raise box["error"]
        return box.get("result")

    def goto(self, url, referer=None):
        self.call(lambda page: page.goto(url, referer=referer, wait_until="domcontentloaded",
                                         timeout=GOTO_TIMEOUT_MS))

    def evaluate(self, js, arg=None, main_world=False):
        """Run js in the page; main_world=True sees the page's own globals
        (window.grecaptcha)."""
        return self.call(lambda page: page.evaluate(js, arg, isolated_context=not main_world))

    def close(self):
        self._jobs.put(None)
        self._thread.join(timeout=15)
        shutil.rmtree(self._profile_dir, ignore_errors=True)
