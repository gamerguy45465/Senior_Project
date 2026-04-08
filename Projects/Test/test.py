import sys
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk


def hello():
    return "Hello World"


class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Hello World")
        self.set_default_size(400, 200)

        text_view = Gtk.TextView(editable=False, cursor_visible=False)
        text_buffer = text_view.get_buffer()
        text_buffer.set_text(hello())

        self.add(text_view)


class HelloWorldApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.example.helloworld")

    def do_activate(self):
        window = self.props.active_window
        if not window:
            window = MainWindow(self)
        window.present()


if __name__ == "__main__":
    app = HelloWorldApp()
    app.run(sys.argv)
