# ARandR -- Another XRandR GUI
# Copyright (C) 2008 -- 2011 chrysn <chrysn@fsfe.org>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Demo application, primarily used to make sure the screenlayout library can be used independent of ARandR.

Run by calling the main() function."""

# pylint: disable=wrong-import-position

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from . import widget


def main():
    window = Gtk.Window()
    window.connect('destroy', Gtk.main_quit)

    arandr = widget.ARandRWidget(window=window)
    arandr.load_from_x()

    reload_button = Gtk.Button("Reload")
    reload_button.connect('clicked', lambda *args: arandr.load_from_x())

    apply_button = Gtk.Button("Apply")
    apply_button.connect('clicked', lambda *args: arandr.save_to_x())

    vbox = Gtk.VBox()
    window.add(vbox)
    vbox.add(arandr)
    vbox.add(reload_button)
    vbox.add(apply_button)
    window.set_title('Simple ARandR Widget Demo')
    window.show_all()
    Gtk.main()
