"""
ARandR -- Another XRandR GUI
Copyright (C) 2008 -- 2011 chrysn <chrysn@fsfe.org>
copyright (C) 2019 actionless <actionless.loveless@gmail.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
# pylint: disable=wrong-import-position,missing-docstring,fixme

from __future__ import division
import os
import stat

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('PangoCairo', '1.0')
from gi.repository import GObject, Gtk, Pango, PangoCairo, Gdk, GLib

from .snap import Snap
from .xrandr import XRandR, Feature
from .auxiliary import Position, NORMAL, ROTATIONS, InadequateConfiguration
from .i18n import _


class ARandRWidget(Gtk.DrawingArea):

    sequence = None
    _lastclick = None
    _draggingoutput = None
    _draggingfrom = None
    _draggingsnap = None
    horizontal_snap = True
    vertical_snap = True

    __gsignals__ = {
        # 'expose-event':'override', # FIXME: still needed?
        'changed': (GObject.SIGNAL_RUN_LAST, GObject.TYPE_NONE, ()),
    }

    def __init__(self, window, factor=8, display=None, force_version=False):
        super(ARandRWidget, self).__init__()

        self.window = window
        self._factor = factor

        self.set_size_request(
            1024 // self.factor, 1024 // self.factor
        )  # best guess for now

        self.connect('button-press-event', self.click)
        self.set_events(Gdk.EventType.BUTTON_PRESS)

        self.setup_draganddrop()

        self._xrandr = XRandR(display=display, force_version=force_version)

        self.connect('draw', self.do_expose_event)

    #################### widget features ####################

    def _set_factor(self, fac):
        self._factor = fac
        self._update_size_request()
        self._force_repaint()

    factor = property(lambda self: self._factor, _set_factor)

    def abort_if_unsafe(self):
        if not [x for x in self._xrandr.configuration.outputs.values() if x.active]:
            dialog = Gtk.MessageDialog(
                None, Gtk.DialogFlags.MODAL, Gtk.MessageType.WARNING, Gtk.ButtonsType.YES_NO,
                _(
                    "Your configuration does not include an active monitor. "
                    "Do you want to apply the configuration?"
                )
            )
            result = dialog.run()
            dialog.destroy()
            if result == Gtk.ResponseType.YES:
                return False
            return True
        return False

    def error_message(self, message):  # pylint: disable=no-self-use
        dialog = Gtk.MessageDialog(
            None, Gtk.DialogFlags.MODAL,
            Gtk.MessageType.ERROR, Gtk.ButtonsType.CLOSE,
            message
        )
        dialog.run()
        dialog.destroy()

    def _update_size_request(self):
        # this ignores that some outputs might not support rotation,
        # but will always err at the side of caution.
        max_gapless = sum(
            max(output.size) if output.active else 0
            for output in self._xrandr.configuration.outputs.values()
        )
        # have some buffer
        usable_size = int(max_gapless * 1.1)
        # don't request too large a window, but make sure very possible compination fits
        xdim = min(self._xrandr.state.virtual.max[0], usable_size)
        ydim = min(self._xrandr.state.virtual.max[1], usable_size)
        self.set_size_request(xdim // self.factor, ydim // self.factor)

    #################### loading ####################

    def load_from_file(self, file):
        data = open(file).read()
        template = self._xrandr.load_from_string(data)
        self._xrandr_was_reloaded()
        return template

    def load_from_x(self):
        self._xrandr.load_from_x()
        self._xrandr_was_reloaded()
        return self._xrandr.DEFAULTTEMPLATE

    def _xrandr_was_reloaded(self):
        self.sequence = sorted(self._xrandr.outputs)
        self._lastclick = (-1, -1)

        self._update_size_request()
        if self.window:
            self._force_repaint()
        self.emit('changed')

    def save_to_x(self):
        self._xrandr.save_to_x()
        self.load_from_x()

    def save_to_file(self, file, template=None, additional=None):
        data = self._xrandr.save_to_shellscript_string(template, additional)
        open(file, 'w').write(data)
        os.chmod(file, stat.S_IRWXU)
        self.load_from_file(file)

    #################### doing changes ####################

    def _set_something(self, which, output_name, data):
        old = getattr(self._xrandr.configuration.outputs[output_name], which)
        setattr(self._xrandr.configuration.outputs[output_name], which, data)
        try:
            self._xrandr.check_configuration()
        except InadequateConfiguration:
            setattr(self._xrandr.configuration.outputs[output_name], which, old)
            raise

        self._force_repaint()
        self.emit('changed')

    def set_position(self, output_name, pos):
        self._set_something('position', output_name, pos)

    def set_rotation(self, output_name, rot):
        self._set_something('rotation', output_name, rot)

    def set_resolution(self, output_name, res):
        self._set_something('mode', output_name, res)

    def set_primary(self, output_name, primary):
        output = self._xrandr.configuration.outputs[output_name]

        if primary and not output.primary:
            for output_2 in self._xrandr.outputs:
                self._xrandr.configuration.outputs[output_2].primary = False
            output.primary = True
        elif not primary and output.primary:
            output.primary = False
        else:
            return

        self._force_repaint()
        self.emit('changed')

    def set_active(self, output_name, active):
        virtual_state = self._xrandr.state.virtual
        output = self._xrandr.configuration.outputs[output_name]

        if not active and output.active:
            output.active = False
            # don't delete: allow user to re-enable without state being lost
        if active and not output.active:
            if hasattr(output, 'position'):
                output.active = True  # nothing can go wrong, position already set
            else:
                pos = Position((0, 0))
                for mode in self._xrandr.state.outputs[output_name].modes:
                    # determine first possible mode
                    if mode[0] <= virtual_state.max[0] and mode[1] <= virtual_state.max[1]:
                        first_mode = mode
                        break
                else:
                    raise InadequateConfiguration(
                        "Smallest mode too large for virtual.")

                output.active = True
                output.position = pos
                output.mode = first_mode
                output.rotation = NORMAL

        self._force_repaint()
        self.emit('changed')

    #################### painting ####################

    def do_expose_event(self, _event, context):
        context.rectangle(
            0, 0,
            self._xrandr.state.virtual.max[0] // self.factor,
            self._xrandr.state.virtual.max[1] // self.factor
        )
        context.clip()

        # clear
        context.set_source_rgb(0, 0, 0)
        context.rectangle(0, 0, *self.window.get_size())
        context.fill()
        context.save()

        context.scale(1 / self.factor, 1 / self.factor)
        context.set_line_width(self.factor * 1.5)

        self._draw(self._xrandr, context)

    def _draw(self, xrandr, context):  # pylint: disable=too-many-locals
        cfg = xrandr.configuration
        state = xrandr.state

        context.set_source_rgb(0.25, 0.25, 0.25)
        context.rectangle(0, 0, *state.virtual.max)
        context.fill()

        context.set_source_rgb(0.5, 0.5, 0.5)
        context.rectangle(0, 0, *cfg.virtual)
        context.fill()

        for output_name in self.sequence:
            output = cfg.outputs[output_name]
            if not output.active:
                continue

            rect = (output.tentative_position if hasattr(
                output, 'tentative_position') else output.position) + tuple(output.size)
            center = rect[0] + rect[2] / 2, rect[1] + rect[3] / 2

            # paint rectangle
            context.set_source_rgba(1, 1, 1, 0.7)
            context.rectangle(*rect)
            context.fill()
            context.set_source_rgb(0, 0, 0)
            context.rectangle(*rect)
            context.stroke()

            # set up for text
            context.save()
            textwidth = rect[3 if output.rotation.is_odd else 2]
            widthperchar = textwidth / len(output_name)
            # i think this looks nice and won't overflow even for wide fonts
            textheight = int(widthperchar * 0.8)

            newdescr = Pango.FontDescription("sans")
            newdescr.set_size(textheight * Pango.SCALE)

            # create text
            output_name_markup = GLib.markup_escape_text(output_name)
            layout = PangoCairo.create_layout(context)
            layout.set_font_description(newdescr)
            if output.primary:
                output_name_markup = "<u>%s</u>" % output_name_markup

            layout.set_markup(output_name_markup, -1)

            # position text
            layoutsize = layout.get_pixel_size()
            layoutoffset = -layoutsize[0] / 2, -layoutsize[1] / 2
            context.move_to(*center)
            context.rotate(output.rotation.angle)
            context.rel_move_to(*layoutoffset)

            # paint text
            PangoCairo.show_layout(context, layout)
            context.restore()

    def _force_repaint(self):
        # using self.allocation as rect is offset by the menu bar.
        self.queue_draw_area(
            0, 0,
            self._xrandr.state.virtual.max[0] // self.factor,
            self._xrandr.state.virtual.max[1] // self.factor
        )
        # this has the side effect of not painting out of the available
        # region output_name drag and drop

    #################### click handling ####################

    def click(self, _widget, event):
        undermouse = self._get_point_outputs(event.x, event.y)
        if event.button == 1 and undermouse:
            which = self._get_point_active_output(event.x, event.y)
            # this was the second click to that stack
            if self._lastclick == (event.x, event.y):
                # push the highest of the undermouse windows below the lowest
                newpos = min(self.sequence.index(a) for a in undermouse)
                self.sequence.remove(which)
                self.sequence.insert(newpos, which)
                # sequence changed
                which = self._get_point_active_output(event.x, event.y)
            # pull the clicked window to the absolute top
            self.sequence.remove(which)
            self.sequence.append(which)

            self._lastclick = (event.x, event.y)
            self._force_repaint()
        if event.button == 3:
            if undermouse:
                target = [a for a in self.sequence if a in undermouse][-1]
                menu = self._contextmenu(target)
                menu.popup(None, None, None, None, event.button, event.time)
            else:
                menu = self.contextmenu()
                menu.popup(None, None, None, None, event.button, event.time)

        # deposit for drag and drop until better way found to determine exact starting coordinates
        self._lastclick = (event.x, event.y)

    def _get_point_outputs(self, x, y):
        x, y = x * self.factor, y * self.factor
        outputs = set()
        for output_name, output in self._xrandr.configuration.outputs.items():
            if not output.active:
                continue
            if (
                    output.position[0] - self.factor <= x <= output.position[0] + output.size[0] + self.factor
            ) and (
                output.position[1] - self.factor <= y <= output.position[1] + output.size[1] + self.factor
            ):
                outputs.add(output_name)
        return outputs

    def _get_point_active_output(self, x, y):
        undermouse = self._get_point_outputs(x, y)
        if not undermouse:
            raise IndexError("No output here.")
        active = [a for a in self.sequence if a in undermouse][-1]
        return active

    #################### context menu ####################

    def contextmenu(self):
        menu = Gtk.Menu()
        for output_name in self._xrandr.outputs:
            output_config = self._xrandr.configuration.outputs[output_name]
            output_state = self._xrandr.state.outputs[output_name]

            i = Gtk.MenuItem(output_name)
            i.props.submenu = self._contextmenu(output_name)
            menu.add(i)

            if not output_config.active and not output_state.connected:
                i.props.sensitive = False
        menu.show_all()
        return menu

    def _contextmenu(self, output_name):  # pylint: disable=too-many-locals
        menu = Gtk.Menu()
        output_config = self._xrandr.configuration.outputs[output_name]
        output_state = self._xrandr.state.outputs[output_name]

        enabled = Gtk.CheckMenuItem(_("Active"))
        enabled.props.active = output_config.active
        enabled.connect('activate', lambda menuitem: self.set_active(
            output_name, menuitem.props.active))

        menu.add(enabled)

        if output_config.active:
            if Feature.PRIMARY in self._xrandr.features:
                primary = Gtk.CheckMenuItem(_("Primary"))
                primary.props.active = output_config.primary
                primary.connect('activate', lambda menuitem: self.set_primary(
                    output_name, menuitem.props.active))
                menu.add(primary)

            res_m = Gtk.Menu()
            for mode in output_state.modes:
                i = Gtk.CheckMenuItem(str(mode))
                i.props.draw_as_radio = True
                i.props.active = (output_config.mode.name == mode.name)

                def _res_set(_menuitem, output_name, mode):
                    try:
                        self.set_resolution(output_name, mode)
                    except InadequateConfiguration as exc:
                        self.error_message(
                            _("Setting this resolution is not possible here: %s") % exc
                        )
                i.connect('activate', _res_set, output_name, mode)
                res_m.add(i)

            or_m = Gtk.Menu()
            for rotation in ROTATIONS:
                i = Gtk.CheckMenuItem("%s" % rotation)
                i.props.draw_as_radio = True
                i.props.active = (output_config.rotation == rotation)

                def _rot_set(_menuitem, output_name, rotation):
                    try:
                        self.set_rotation(output_name, rotation)
                    except InadequateConfiguration as exc:
                        self.error_message(
                            _("This orientation is not possible here: %s") % exc
                        )
                i.connect('activate', _rot_set, output_name, rotation)
                if rotation not in output_state.rotations:
                    i.props.sensitive = False
                or_m.add(i)

            res_i = Gtk.MenuItem(_("Resolution"))
            res_i.props.submenu = res_m
            or_i = Gtk.MenuItem(_("Orientation"))
            or_i.props.submenu = or_m

            menu.add(res_i)
            menu.add(or_i)

        menu.show_all()
        return menu

    #################### drag&drop ####################

    def setup_draganddrop(self):
        self.drag_source_set(
            Gdk.ModifierType.BUTTON1_MASK,
            [Gtk.TargetEntry('screenlayout-output',
                             Gtk.TargetFlags.SAME_WIDGET, 0)],
            0
        )
        self.drag_dest_set(
            0,
            [Gtk.TargetEntry('screenlayout-output',
                             Gtk.TargetFlags.SAME_WIDGET, 0)],
            0
        )
        # self.drag_source_set(Gdk.BUTTON1_MASK, [], 0)
        # self.drag_dest_set(0, [], 0)

        self._draggingfrom = None
        self._draggingoutput = None
        self.connect('drag-begin', self._dragbegin_cb)
        self.connect('drag-motion', self._dragmotion_cb)
        self.connect('drag-drop', self._dragdrop_cb)
        self.connect('drag-end', self._dragend_cb)

        self._lastclick = (0, 0)

    def _dragbegin_cb(self, widget, context):
        try:
            output = self._get_point_active_output(*self._lastclick)
        except IndexError:
            # FIXME: abort?
            Gtk.drag_set_icon_stock(context, Gtk.STOCK_CANCEL, 10, 10)
            return

        self._draggingoutput = output
        self._draggingfrom = self._lastclick
        Gtk.drag_set_icon_stock(context, Gtk.STOCK_FULLSCREEN, 10, 10)

        self._draggingsnap = Snap(
            self._xrandr.configuration.outputs[self._draggingoutput].size,
            self.factor * 5,
            [(Position((0, 0)), self._xrandr.state.virtual.max)] + [
                (virtual_state.position, virtual_state.size)
                for (k, virtual_state) in self._xrandr.configuration.outputs.items()
                if k != self._draggingoutput and virtual_state.active
            ],
            widget.horizontal_snap,
            widget.vertical_snap
        )

    def _dragmotion_cb(self, widget, context, x, y, time):  # pylint: disable=too-many-arguments
        # if not 'screenlayout-output' in context.list_targets():  # from outside
            # return False
        if not self._draggingoutput:  # from void; should be already aborted
            return False

        Gdk.drag_status(context, Gdk.DragAction.MOVE, time)

        rel = x - self._draggingfrom[0], y - self._draggingfrom[1]

        oldpos = self._xrandr.configuration.outputs[self._draggingoutput].position
        newpos = Position(
            (oldpos[0] + self.factor * rel[0], oldpos[1] + self.factor * rel[1]))
        self._xrandr.configuration.outputs[
            self._draggingoutput
        ].tentative_position = self._draggingsnap.suggest(newpos)
        self._force_repaint()

        return True

    def _dragdrop_cb(self, widget, context, x, y, time):  # pylint: disable=too-many-arguments
        if not self._draggingoutput:
            return

        try:
            self.set_position(
                self._draggingoutput,
                self._xrandr.configuration.outputs[self._draggingoutput].tentative_position
            )
        except InadequateConfiguration:
            context.finish(False, False, time)
            # raise # snapping back to the original position should be enought feedback

        context.finish(True, False, time)

    def _dragend_cb(self, widget, context):
        try:
            del self._xrandr.configuration.outputs[self._draggingoutput].tentative_position
        except (KeyError, AttributeError):
            pass  # already reloaded
        self._draggingoutput = None
        self._draggingfrom = None
        self._force_repaint()
