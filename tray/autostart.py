"""Autostart über HKCU\\...\\Run. Logik gegen ein injizierbares Backend testbar."""

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "Supplierplan"


def enable_autostart(reg, name, command):
    reg.set_value(name, command)


def disable_autostart(reg, name):
    reg.delete_value(name)


def is_autostart(reg, name):
    return reg.get_value(name) is not None


class WinRegistry:
    """Echtes Backend (nur auf Windows). Kapselt winreg auf den Run-Key."""
    def __init__(self):
        import winreg
        self._winreg = winreg
        self._root = winreg.HKEY_CURRENT_USER

    def set_value(self, name, value):
        wr = self._winreg
        with wr.CreateKey(self._root, RUN_KEY) as k:
            wr.SetValueEx(k, name, 0, wr.REG_SZ, value)

    def delete_value(self, name):
        wr = self._winreg
        try:
            with wr.OpenKey(self._root, RUN_KEY, 0, wr.KEY_SET_VALUE) as k:
                wr.DeleteValue(k, name)
        except FileNotFoundError:
            pass

    def get_value(self, name):
        wr = self._winreg
        try:
            with wr.OpenKey(self._root, RUN_KEY, 0, wr.KEY_READ) as k:
                val, _ = wr.QueryValueEx(k, name)
                return val
        except FileNotFoundError:
            return None
