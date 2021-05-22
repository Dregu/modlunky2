import logging
import selectors
import subprocess
import threading
import os
import tkinter as tk
from tkinter import ttk

from modlunky2.constants import BASE_DIR
from modlunky2.ui.widgets import Tab

logger = logging.getLogger("modlunky2")


def s99_client_path(launcher_exe):
    if launcher_exe:
        client_dir = launcher_exe.resolve().parent
    else:
        client_dir = BASE_DIR / "../../dist"

    if "nt" in os.name:
        return client_dir / "s99-client.exe"

    return client_dir / "s99-client"


class S99Client(threading.Thread):
    def __init__(
        self,
        exe_path,
        api_token,
    ):
        super().__init__()
        self.select_timeout = 0.1
        self.shut_down = False
        self.exe_path = exe_path
        self.api_token = api_token

    def run(self):
        if not self.api_token:
            logger.warning("No API Token...")
            return

        if not self.exe_path.exists():
            print(self.exe_path)
            logger.warning("No exe found...")
            return

        env = os.environ.copy()
        env["SFYI_API_TOKEN"] = self.api_token

        logger.info("Launching S99 Client")
        cmd = [f"{self.exe_path}"]

        client_proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            env=env,
        )

        shutting_down = False
        watching = {client_proc.stdout, client_proc.stderr}

        sel = selectors.DefaultSelector()
        for to_watch in watching:
            sel.register(to_watch, selectors.EVENT_READ)

        while watching:
            if not shutting_down and self.shut_down:
                shutting_down = True
                client_proc.kill()

            events = sel.select(timeout=self.select_timeout)
            for (key, _) in events:
                line = key.fileobj.readline().strip()

                if not line:
                    watching.remove(key.fileobj)
                    sel.unregister(key.fileobj)
                    break

                if key.fileobj is client_proc.stdout:
                    logger.info(line)
                else:
                    logger.warning(line)

        logger.info("Client closed.")


class S99Tab(Tab):
    def __init__(self, tab_control, modlunky_config, *args, **kwargs):
        super().__init__(tab_control, *args, **kwargs)
        self.tab_control = tab_control
        self.modlunky_config = modlunky_config

        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.s99_frame = ttk.LabelFrame(self, text="Spelunky 99")
        self.s99_frame.grid(sticky="nsew")

        self.s99_frame.rowconfigure(0, weight=1)
        self.s99_frame.rowconfigure(1, minsize=60)
        self.s99_frame.rowconfigure(2, minsize=60)
        self.s99_frame.columnconfigure(0, weight=1)

        self.welcome_label = ttk.Label(
            self.s99_frame,
            text=(
                "Welcome to the Spelunky 99 Client.\n"
                "Click Connect and then launch the game with Playlunky.\n\n"
                "Note: Make sure you have an API token configured in the Settings tab."
            ),
            anchor="center",
        )
        self.welcome_label.grid(row=0, column=0, sticky="nwe", ipady=30, padx=(10, 10))

        self.button_connect = ttk.Button(
            self.s99_frame,
            text="Connect",
            command=self.connect,
            state=tk.DISABLED,
        )
        self.button_connect.grid(row=1, column=0, pady=5, padx=5, sticky="nswe")

        self.button_disconnect = ttk.Button(
            self.s99_frame,
            text="Disconnect",
            command=self.disconnect,
            state=tk.DISABLED,
        )
        self.button_disconnect.grid(row=2, column=0, pady=5, padx=5, sticky="nswe")

        self.client_thread = None
        self.after(1000, self.after_client_thread)
        self.render_buttons()

    @property
    def client_path(self):
        return s99_client_path(self.modlunky_config.launcher_exe)

    def render_buttons(self):
        api_token = self.modlunky_config.config_file.spelunky_fyi_api_token

        if not api_token:
            self.disable_connect_button()
            self.disable_disconnect_button()
            return

        if self.client_thread is None:
            self.enable_connect_button()
            self.disable_disconnect_button()
        else:
            self.enable_connect_button()
            self.disable_disconnect_button()

    def after_client_thread(self):
        try:
            if self.client_thread is None:
                return

            if self.client_thread.is_alive():
                return

            # Process was running but has since exited.
            self.client_thread = None
            self.render_buttons()
        finally:
            self.after(1000, self.after_client_thread)

    def enable_connect_button(self):
        self.button_connect["state"] = tk.NORMAL

    def disable_connect_button(self):
        self.button_connect["state"] = tk.DISABLED

    def enable_disconnect_button(self):
        self.button_disconnect["state"] = tk.NORMAL

    def disable_disconnect_button(self):
        self.button_disconnect["state"] = tk.DISABLED

    def disconnect(self):
        if self.client_thread:
            self.client_thread.shut_down = True
        self.render_buttons()

    def connect(self):
        self.disable_connect_button()
        self.enable_disconnect_button()

        api_token = self.modlunky_config.config_file.spelunky_fyi_api_token
        print()
        self.client_thread = S99Client(self.client_path, api_token)
        self.client_thread.start()

    def client_closed(self):
        self.enable_connect_button()
        self.disable_disconnect_button()

    def destroy(self) -> None:
        self.disconnect()
        return super().destroy()
