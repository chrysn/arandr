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
# pylint: disable=wrong-import-position,missing-docstring,attribute-defined-outside-init

from __future__ import division
import os
import stat
import gettext

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('PangoCairo', '1.0')
from gi.repository import GObject, Gtk, Pango, PangoCairo, Gdk

from .snap import Snap
from .xrandr import XRandR, Feature
from .auxiliary import Position, NORMAL, ROTATIONS, InadequateConfiguration


gettext.install('arandr')


class ARandRWidget(Gtk.DrawingArea):

    __gsignals__ = {
        # 'expose-event':'override', # FIXME: still needed?
        'changed': (GObject.SIGNAL_RUN_LAST, GObject.TYPE_NONE, ()),
    }

    def __init__(self, window, factor=8, display=None, force_version=False):
        super(ARandRWidget, self).__init__()

        self.window = window
        self._factor = factor

        self.set_size_request(1024//self.factor, 1024 //
                              self.factor)  # best guess for now

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
                _("Your configuration does not include an active monitor. Do you want to apply the configuration?")
            )
            result = dialog.run()
            dialog.destroy()
            if result == Gtk.ResponseType.YES:
                return False
            else:
                return True
        return False

    def error_message(self, message):
        dialog = Gtk.MessageDialog(
            None, Gtk.DialogFlags.MODAL,
            Gtk.MessageType.ERROR, Gtk.ButtonsType.CLOSE,
            message
        )
        dialog.run()
        dialog.destroy()

    def _update_size_request(self):
        # this ignores that some outputs might not support rotation, but will always err at the side of caution.
        max_gapless = sum(max(
            o.size) if o.active else 0 for o in self._xrandr.configuration.outputs.values())
        # have some buffer
        usable_size = int(max_gapless * 1.1)
        # don't request too large a window, but make sure very possible compination fits
        xdim = min(self._xrandr.state.virtual.max[0], usable_size)
        ydim = min(self._xrandr.state.virtual.max[1], usable_size)
        self.set_size_request(xdim//self.factor, ydim//self.factor)

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

    def _set_something(self, which, on, data):
        old = getattr(self._xrandr.configuration.outputs[on], which)
        setattr(self._xrandr.configuration.outputs[on], which, data)
        try:
            self._xrandr.check_configuration()
        except InadequateConfiguration:
            setattr(self._xrandr.configuration.outputs[on], which, old)
            raise

        self._force_repaint()
        self.emit('changed')

    def set_position(self, on, pos):
        self._set_something('position', on, pos)

    def set_rotation(self, on, rot):
        self._set_something('rotation', on, rot)

    def set_resolution(self, on, res):
        self._set_something('mode', on, res)

    def set_primary(self, on, primary):
        o = self._xrandr.configuration.outputs[on]

        if primary and not o.primary:
            for o2 in self._xrandr.outputs:
                self._xrandr.configuration.outputs[o2].primary = False
            o.primary = True
        elif not primary and o.primary:
            o.primary = False
        else:
            return

        self._force_repaint()
        self.emit('changed')

    def set_active(self, on, active):
        v = self._xrandr.state.virtual
        o = self._xrandr.configuration.outputs[on]

        if not active and o.active:
            o.active = False
            # don't delete: allow user to re-enable without state being lost
        if active and not o.active:
            if hasattr(o, 'position'):
                o.active = True  # nothing can go wrong, position already set
            else:
                pos = Position((0, 0))
                for m in self._xrandr.state.outputs[on].modes:
                    # determine first possible mode
                    if m[0] <= v.max[0] and m[1] <= v.max[1]:
                        mode = m
                        break
                else:
                    raise InadequateConfiguration(
                        "Smallest mode too large for virtual.")

                o.active = True
                o.position = pos
                o.mode = mode
                o.rotation = NORMAL

        self._force_repaint()
        self.emit('changed')

    #################### painting ####################

    def do_expose_event(self, event, cr):
        # cr = PangoCairo.CairoContext(self.window.cairo_create())
        # cr.rectangle(event.area.x, event.area.y,
                     # event.area.width, event.area.height)
        cr.rectangle(
            0, 0, self._xrandr.state.virtual.max[0]//self.factor, self._xrandr.state.virtual.max[1]//self.factor
        )
        cr.clip()

        # clear
        cr.set_source_rgb(0, 0, 0)
        cr.rectangle(0, 0, *self.window.get_size())
        cr.fill()
        cr.save()

        cr.scale(1/self.factor, 1/self.factor)
        cr.set_line_width(self.factor*1.5)

        self._draw(self._xrandr, cr)

    def _draw(self, xrandr, cr):
        cfg = xrandr.configuration
        state = xrandr.state

        cr.set_source_rgb(0.25, 0.25, 0.25)
        cr.rectangle(0, 0, *state.virtual.max)
        cr.fill()

        cr.set_source_rgb(0.5, 0.5, 0.5)
        cr.rectangle(0, 0, *cfg.virtual)
        cr.fill()

        for on in self.sequence:
            o = cfg.outputs[on]
            if not o.active:
                continue

            rect = (o.tentative_position if hasattr(
                o, 'tentative_position') else o.position) + tuple(o.size)
            center = rect[0]+rect[2]/2, rect[1]+rect[3]/2

            # paint rectangle
            cr.set_source_rgba(1, 1, 1, 0.7)
            cr.rectangle(*rect)
            cr.fill()
            cr.set_source_rgb(0, 0, 0)
            cr.rectangle(*rect)
            cr.stroke()

            # set up for text
            cr.save()
            textwidth = rect[3 if o.rotation.is_odd else 2]
            widthperchar = textwidth/len(on)
            # i think this looks nice and won't overflow even for wide fonts
            textheight = int(widthperchar * 0.8)

            newdescr = Pango.FontDescription("sans")
            newdescr.set_size(textheight * Pango.SCALE)

            # create text
            layout = PangoCairo.create_layout(cr)
            layout.set_font_description(newdescr)
            if o.primary:
                underline_attrs = Pango.parse_markup("<u>test</u>", -1, "0")[1]
                # attrs = Pango.AttrList()
                # attr = Pango.Attribute()
                # attr_class = Pango.AttrClass()
                # attr_class.type = Pango.AttrType.UNDERLINE
                # attr.init(attr_class)
                # attrs.insert(attr)
                # attrs.insert(Pango.Underline.SINGLE)
                # layout.set_attributes(attrs)
                layout.set_attributes(underline_attrs)

            layout.set_text(on, -1)

            # position text
            layoutsize = layout.get_pixel_size()
            layoutoffset = -layoutsize[0]/2, -layoutsize[1]/2
            cr.move_to(*center)
            cr.rotate(o.rotation.angle)
            cr.rel_move_to(*layoutoffset)

            # paint text
            PangoCairo.show_layout(cr, layout)
            cr.restore()

    def _force_repaint(self):
        # using self.allocation as rect is offset by the menu bar.
        # self.window.invalidate_rect(Gdk.Rectangle(
            # 0, 0, self._xrandr.state.virtual.max[0]//self.factor, self._xrandr.state.virtual.max[1]//self.factor), False)
        self.queue_draw_area(
            0, 0, self._xrandr.state.virtual.max[0]//self.factor, self._xrandr.state.virtual.max[1]//self.factor
        )
        # this has the side effect of not painting out of the available region on drag and drop

    #################### click handling ####################

    def click(self, widget, event):
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
                m = self._contextmenu(target)
                m.popup(None, None, None, None, event.button, event.time)
            else:
                m = self.contextmenu()
                m.popup(None, None, None, None, event.button, event.time)

        # deposit for drag and drop until better way found to determine exact starting coordinates
        self._lastclick = (event.x, event.y)

    def _get_point_outputs(self, x, y):
        x, y = x*self.factor, y*self.factor
        outputs = set()
        for on, o in self._xrandr.configuration.outputs.items():
            if not o.active:
                continue
            if o.position[0]-self.factor <= x <= o.position[0]+o.size[0]+self.factor and o.position[1]-self.factor <= y <= o.position[1]+o.size[1]+self.factor:
                outputs.add(on)
        return outputs

    def _get_point_active_output(self, x, y):
        undermouse = self._get_point_outputs(x, y)
        if not undermouse:
            raise IndexError("No output here.")
        active = [a for a in self.sequence if a in undermouse][-1]
        return active

    #################### context menu ####################

    def contextmenu(self):
        m = Gtk.Menu()
        for on in self._xrandr.outputs:
            oc = self._xrandr.configuration.outputs[on]
            os = self._xrandr.state.outputs[on]

            i = Gtk.MenuItem(on)
            i.props.submenu = self._contextmenu(on)
            m.add(i)

            if not oc.active and not os.connected:
                i.props.sensitive = False
        m.show_all()
        return m

    def _contextmenu(self, on):
        m = Gtk.Menu()
        oc = self._xrandr.configuration.outputs[on]
        os = self._xrandr.state.outputs[on]

        enabled = Gtk.CheckMenuItem(_("Active"))
        enabled.props.active = oc.active
        enabled.connect('activate', lambda menuitem: self.set_active(
            on, menuitem.props.active))

        m.add(enabled)

        if oc.active:
            if Feature.PRIMARY in self._xrandr.features:
                primary = Gtk.CheckMenuItem(_("Primary"))
                primary.props.active = oc.primary
                primary.connect('activate', lambda menuitem: self.set_primary(
                    on, menuitem.props.active))
                m.add(primary)

            res_m = Gtk.Menu()
            for r in os.modes:
                i = Gtk.CheckMenuItem(str(r))
                i.props.draw_as_radio = True
                i.props.active = (oc.mode.name == r.name)

                def _res_set(menuitem, on, r):
                    try:
                        self.set_resolution(on, r)
                    except InadequateConfiguration as e:
                        self.error_message(
                            _("Setting this resolution is not possible here: %s") % e.message)
                i.connect('activate', _res_set, on, r)
                res_m.add(i)

            or_m = Gtk.Menu()
            for r in ROTATIONS:
                i = Gtk.CheckMenuItem("%s" % r)
                i.props.draw_as_radio = True
                i.props.active = (oc.rotation == r)

                def _rot_set(menuitem, on, r):
                    try:
                        self.set_rotation(on, r)
                    except InadequateConfiguration as e:
                        self.error_message(
                            _("This orientation is not possible here: %s") % e.message)
                i.connect('activate', _rot_set, on, r)
                if r not in os.rotations:
                    i.props.sensitive = False
                or_m.add(i)

            res_i = Gtk.MenuItem(_("Resolution"))
            res_i.props.submenu = res_m
            or_i = Gtk.MenuItem(_("Orientation"))
            or_i.props.submenu = or_m

            m.add(res_i)
            m.add(or_i)

        m.show_all()
        return m

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
        #self.drag_source_set(Gdk.BUTTON1_MASK, [], 0)
        #self.drag_dest_set(0, [], 0)

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
            self.factor*5,
            [(Position((0, 0)), self._xrandr.state.virtual.max)]+[
                (v.position, v.size) for (k, v) in self._xrandr.configuration.outputs.items()
                if k != self._draggingoutput and v.active
            ]
        )

    def _dragmotion_cb(self, widget, context, x, y, time):
        # if not 'screenlayout-output' in context.list_targets():  # from outside
            # return False
        if not self._draggingoutput:  # from void; should be already aborted
            return False

        Gdk.drag_status(context, Gdk.DragAction.MOVE, time)

        rel = x-self._draggingfrom[0], y-self._draggingfrom[1]

        oldpos = self._xrandr.configuration.outputs[self._draggingoutput].position
        newpos = Position(
            (oldpos[0]+self.factor*rel[0], oldpos[1]+self.factor*rel[1]))
        self._xrandr.configuration.outputs[self._draggingoutput].tentative_position = self._draggingsnap.suggest(
            newpos)
        self._force_repaint()

        return True

    def _dragdrop_cb(self, widget, context, x, y, time):
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
