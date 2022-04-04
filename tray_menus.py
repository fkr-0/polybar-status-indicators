import json
import subprocess
import sys
import time

import gi

gi.require_version("Gtk", "3.0")

from gi.repository import Gio  # noqa
from gi.repository import GLib  # noqa

from socket_communication import SOCK_PATH, request

DMENU_CMD = ["rofi", "-dmenu", "-i", "-no-sort"]


class Bus:
    def __init__(self, conn, name, path):
        self.conn = conn
        self.name = name
        self.path = path

    def call_sync(self, interface, method, params, params_type, return_type):
        return self.conn.call_sync(
            self.name,
            self.path,
            interface,
            method,
            GLib.Variant(params_type, params),
            GLib.VariantType(return_type),
            Gio.DBusCallFlags.NONE,
            -1,
            None,
        )

    def get_menu_layout(self, *args):
        return self.call_sync(
            "com.canonical.dbusmenu",
            "GetLayout",
            args,
            "(iias)",
            "(u(ia{sv}av))",
        )

    def menu_event(self, *args):
        self.call_sync("com.canonical.dbusmenu", "Event", args, "(isvu)", "()")


def dmenu(_input):
    p = subprocess.Popen(
        DMENU_CMD,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding="utf-8",
    )
    out, _ = p.communicate(_input)
    return out


def format_toggle_value(props):
    toggle_type = props.get("toggle-type", "")
    toggle_value = props.get("toggle-state", -1)

    if toggle_value == 0:
        s = " "
    elif toggle_value == 1:
        s = "X"
    else:
        s = "~"

    if toggle_type == "checkmark":
        return f"[{s}] "
    elif toggle_type == "radio":
        return f"({s}) "
    else:
        return ""


def format_menu_item(item, level=1):
    id, props, children = item

    if not props.get("visible", True):
        return ""
    if props.get("type", "standard") == "separator":
        label = "---"
    else:
        label = format_toggle_value(props) + props.get("label", "")
        if not props.get("enabled", True):
            label = f"({label})"

    indentation = "  " * level
    ret = f"{id}{indentation}{label}\n"
    for child in children:
        ret += format_menu_item(child, level + 1)
    return ret


def show_app_menu(conn, name, path):
    bus = Bus(conn, name, path)
    item = bus.get_menu_layout(0, -1, [])[1]
    menu = format_menu_item(item)
    selected = dmenu(menu)

    if selected:
        id = int(selected.split()[0])
        bus.menu_event(id, "clicked", GLib.Variant("s", ""), time.time())


def send_activate(app_id, app_path):
    try:
        subprocess.run(["busctl", "--user", "call", app_id, app_path, "org.kde.StatusNotifierItem Activate ii 0 0"])
    except Exception as e:
        subprocess.run(["notify-send", str(e)])


if __name__ == "__main__":
    conn = Gio.bus_get_sync(Gio.BusType.SESSION)
    if len(sys.argv) > 2:
        app_id, app_menu_path = sys.argv[1], sys.argv[2]
        show_app_menu(conn, app_id, app_menu_path)
    elif len(sys.argv) == 2 and sys.argv[1] == "apps":
        men = request(SOCK_PATH, {"command": "menu"})
        apps = []
        actions = []
        for k, v in men.items():
            apps.append(k)
        app = dmenu("\n".join(apps)).strip()
        items = men[app]
        show_app_menu(conn, items["name"], items["menu_path"])
    elif len(sys.argv) == 2 and sys.argv[1] == "big_menu":
        men = request(SOCK_PATH, {"command": "menu"})
        m = ""
        busses = {}
        for k, v in men.items():
            name, path = v["name"], v["menu_path"]
            # name = name[1:]
            bus = Bus(conn, name, path)
            busses[k] = bus
            item = bus.get_menu_layout(0, -1, [])[1]
            print(name)
            print(path)
            print(item)
            menuentries = map(lambda x: f"{k}>{x}", format_menu_item(item).split("\n"))
            m += "\n".join(menuentries) + "\n"
        selected = dmenu(m)
        if selected:
            app_split = selected.split(">")
            app = app_split[0]
            id = int(app_split[1].split()[0])
            bus = busses[app]
            bus.menu_event(id, "clicked", GLib.Variant("s", ""), time.time())
        print(selected)
    else:
        db = request(SOCK_PATH, {"command": "debug"})
        print(json.dumps(db, indent=2))
