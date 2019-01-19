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
"""Wrapper around command line xrandr (mostly 1.2 per output features supported)"""
# pylint: disable=too-few-public-methods,wrong-import-position,missing-docstring,fixme

import os
import subprocess
import warnings
from functools import reduce

from .auxiliary import (
    BetterList, Size, Position, Geometry, FileLoadError, FileSyntaxError,
    InadequateConfiguration, Rotation, ROTATIONS, NORMAL, NamedSize,
)
from .i18n import _

SHELLSHEBANG = '#!/bin/sh'


class Feature:
    PRIMARY = 1


class XRandR:
    DEFAULTTEMPLATE = [SHELLSHEBANG, '%(xrandr)s']

    configuration = None
    state = None

    def __init__(self, display=None, force_version=False):
        """Create proxy object and check for xrandr at `display`. Fail with
        untested versions unless `force_version` is True."""
        self.environ = dict(os.environ)
        if display:
            self.environ['DISPLAY'] = display

        version_output = self._output("--version")
        supported_versions = ["1.2", "1.3", "1.4", "1.5"]
        if not any(x in version_output for x in supported_versions) and not force_version:
            raise Exception("XRandR %s required." %
                            "/".join(supported_versions))

        self.features = set()
        if " 1.2" not in version_output:
            self.features.add(Feature.PRIMARY)

    def _get_outputs(self):
        assert self.state.outputs.keys() == self.configuration.outputs.keys()
        return self.state.outputs.keys()
    outputs = property(_get_outputs)

    #################### calling xrandr ####################

    def _output(self, *args):
        proc = subprocess.Popen(
            ("xrandr",) + args,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=self.environ
        )
        ret, err = proc.communicate()
        status = proc.wait()
        if status != 0:
            raise Exception("XRandR returned error code %d: %s" %
                            (status, err))
        if err:
            warnings.warn(
                "XRandR wrote to stderr, but did not report an error (Message was: %r)" % err)
        return ret.decode('utf-8')

    def _run(self, *args):
        self._output(*args)

    #################### loading ####################

    def load_from_string(self, data):
        data = data.replace("%", "%%")
        lines = data.split("\n")
        if lines[-1] == '':
            lines.pop()  # don't create empty last line

        if lines[0] != SHELLSHEBANG:
            raise FileLoadError('Not a shell script.')

        xrandrlines = [i for i, l in enumerate(
            lines) if l.strip().startswith('xrandr ')]
        if not xrandrlines:
            raise FileLoadError('No recognized xrandr command in this shell script.')
        if len(xrandrlines) > 1:
            raise FileLoadError('More than one xrandr line in this shell script.')
        self._load_from_commandlineargs(lines[xrandrlines[0]].strip())
        lines[xrandrlines[0]] = '%(xrandr)s'

        return lines

    def _load_from_commandlineargs(self, commandline):
        self.load_from_x()

        args = BetterList(commandline.split(" "))
        if args.pop(0) != 'xrandr':
            raise FileSyntaxError()
        # first part is empty, exclude empty parts
        options = dict((a[0], a[1:]) for a in args.split('--output') if a)

        for output_name, output_argument in options.items():
            output = self.configuration.outputs[output_name]
            output_state = self.state.outputs[output_name]
            output.primary = False
            if output_argument == ['--off']:
                output.active = False
            else:
                if '--primary' in output_argument:
                    if Feature.PRIMARY in self.features:
                        output.primary = True
                    output_argument.remove('--primary')
                if len(output_argument) % 2 != 0:
                    raise FileSyntaxError()
                parts = [
                    (output_argument[2 * i], output_argument[2 * i + 1])
                    for i in range(len(output_argument) // 2)
                ]
                for part in parts:
                    if part[0] == '--mode':
                        for namedmode in output_state.modes:
                            if namedmode.name == part[1]:
                                output.mode = namedmode
                                break
                        else:
                            raise FileLoadError("Not a known mode: %s" % part[1])
                    elif part[0] == '--pos':
                        output.position = Position(part[1])
                    elif part[0] == '--rotate':
                        if part[1] not in ROTATIONS:
                            raise FileSyntaxError()
                        output.rotation = Rotation(part[1])
                    else:
                        raise FileSyntaxError()
                output.active = True

    def load_from_x(self):  # FIXME -- use a library
        self.configuration = self.Configuration(self)
        self.state = self.State()

        screenline, items = self._load_raw_lines()

        self._load_parse_screenline(screenline)

        for headline, details in items:
            if headline.startswith("  "):
                continue  # a currently disconnected part of the screen i can't currently get any info out of
            if headline == "":
                continue  # noise

            headline = headline.replace(
                'unknown connection', 'unknown-connection')
            hsplit = headline.split(" ")
            output = self.state.Output(hsplit[0])
            assert hsplit[1] in (
                "connected", "disconnected", 'unknown-connection')

            output.connected = (hsplit[1] in ('connected', 'unknown-connection'))

            primary = False
            if 'primary' in hsplit:
                if Feature.PRIMARY in self.features:
                    primary = True
                hsplit.remove('primary')

            if not hsplit[2].startswith("("):
                active = True

                geometry = Geometry(hsplit[2])

                # modeid = hsplit[3].strip("()")

                if hsplit[4] in ROTATIONS:
                    current_rotation = Rotation(hsplit[4])
                else:
                    current_rotation = NORMAL
            else:
                active = False
                geometry = None
                # modeid = None
                current_rotation = None

            output.rotations = set()
            for rotation in ROTATIONS:
                if rotation in headline:
                    output.rotations.add(rotation)

            currentname = None
            for detail, w, h in details:
                name, _mode_raw = detail[0:2]
                mode_id = _mode_raw.strip("()")
                try:
                    size = Size([int(w), int(h)])
                except ValueError:
                    raise Exception(
                        "Output %s parse error: modename %s modeid %s." % (output.name, name, mode_id)
                    )
                if "*current" in detail:
                    currentname = name
                for x in ["+preferred", "*current"]:
                    if x in detail:
                        detail.remove(x)

                for old_mode in output.modes:
                    if old_mode.name == name:
                        if tuple(old_mode) != tuple(size):
                            warnings.warn((
                                "Supressing duplicate mode %s even "
                                "though it has different resolutions (%s, %s)."
                            ) % (name, size, old_mode))
                        break
                else:
                    # the mode is really new
                    output.modes.append(NamedSize(size, name=name))

            self.state.outputs[output.name] = output
            self.configuration.outputs[output.name] = self.configuration.OutputConfiguration(
                active, primary, geometry, current_rotation, currentname
            )

    def _load_raw_lines(self):
        output = self._output("--verbose")
        items = []
        screenline = None
        for line in output.split('\n'):
            if line.startswith("Screen "):
                assert screenline is None
                screenline = line
            elif line.startswith('\t'):
                continue
            elif line.startswith(2 * ' '):  # [mode, width, height]
                line = line.strip()
                if reduce(bool.__or__, [line.startswith(x + ':') for x in "hv"]):
                    line = line[-len(line):line.index(" start") - len(line)]
                    items[-1][1][-1].append(line[line.rindex(' '):])
                else:  # mode
                    items[-1][1].append([line.split()])
            else:
                items.append([line, []])
        return screenline, items

    def _load_parse_screenline(self, screenline):
        assert screenline is not None
        ssplit = screenline.split(" ")

        ssplit_expect = ["Screen", None, "minimum", None, "x", None,
                         "current", None, "x", None, "maximum", None, "x", None]
        assert all(a == b for (a, b) in zip(
            ssplit, ssplit_expect) if b is not None)

        self.state.virtual = self.state.Virtual(
            min_mode=Size((int(ssplit[3]), int(ssplit[5][:-1]))),
            max_mode=Size((int(ssplit[11]), int(ssplit[13])))
        )
        self.configuration.virtual = Size(
            (int(ssplit[7]), int(ssplit[9][:-1]))
        )

    #################### saving ####################

    def save_to_shellscript_string(self, template=None, additional=None):
        """
        Return a shellscript that will set the current configuration.
        Output can be parsed by load_from_string.

        You may specify a template, which must contain a %(xrandr)s parameter
        and optionally others, which will be filled from the additional dictionary.
        """
        if not template:
            template = self.DEFAULTTEMPLATE
        template = '\n'.join(template) + '\n'

        data = {
            'xrandr': "xrandr " + " ".join(self.configuration.commandlineargs())
        }
        if additional:
            data.update(additional)

        return template % data

    def save_to_x(self):
        self.check_configuration()
        self._run(*self.configuration.commandlineargs())

    def check_configuration(self):
        vmax = self.state.virtual.max

        for output_name in self.outputs:
            output_config = self.configuration.outputs[output_name]
            # output_state = self.state.outputs[output_name]

            if not output_config.active:
                continue

            # we trust users to know what they are doing
            # (e.g. widget: will accept current mode,
            # but not offer to change it lacking knowledge of alternatives)
            #
            # if output_config.rotation not in output_state.rotations:
            #    raise InadequateConfiguration("Rotation not allowed.")
            # if output_config.mode not in output_state.modes:
            #    raise InadequateConfiguration("Mode not allowed.")

            x = output_config.position[0] + output_config.size[0]
            y = output_config.position[1] + output_config.size[1]

            if x > vmax[0] or y > vmax[1]:
                raise InadequateConfiguration(
                    _("A part of an output is outside the virtual screen."))

            if output_config.position[0] < 0 or output_config.position[1] < 0:
                raise InadequateConfiguration(
                    _("An output is outside the virtual screen."))

    #################### sub objects ####################

    class State:
        """Represents everything that can not be set by xrandr."""

        virtual = None

        def __init__(self):
            self.outputs = {}

        def __repr__(self):
            return '<%s for %d Outputs, %d connected>' % (
                type(self).__name__, len(self.outputs),
                len([x for x in self.outputs.values() if x.connected])
            )

        class Virtual:
            def __init__(self, min_mode, max_mode):
                self.min = min_mode
                self.max = max_mode

        class Output:
            rotations = None
            connected = None

            def __init__(self, name):
                self.name = name
                self.modes = []

            def __repr__(self):
                return '<%s %r (%d modes)>' % (type(self).__name__, self.name, len(self.modes))

    class Configuration:
        """
        Represents everything that can be set by xrandr
        (and is therefore subject to saving and loading from files)
        """

        virtual = None

        def __init__(self, xrandr):
            self.outputs = {}
            self._xrandr = xrandr

        def __repr__(self):
            return '<%s for %d Outputs, %d active>' % (
                type(self).__name__, len(self.outputs),
                len([x for x in self.outputs.values() if x.active])
            )

        def commandlineargs(self):
            args = []
            for output_name, output in self.outputs.items():
                args.append("--output")
                args.append(output_name)
                if not output.active:
                    args.append("--off")
                else:
                    if Feature.PRIMARY in self._xrandr.features:
                        if output.primary:
                            args.append("--primary")
                    args.append("--mode")
                    args.append(str(output.mode.name))
                    args.append("--pos")
                    args.append(str(output.position))
                    args.append("--rotate")
                    args.append(output.rotation)
            return args

        class OutputConfiguration:

            def __init__(self, active, primary, geometry, rotation, modename):
                self.active = active
                self.primary = primary
                if active:
                    self.position = geometry.position
                    self.rotation = rotation
                    if rotation.is_odd:
                        self.mode = NamedSize(
                            Size(reversed(geometry.size)), name=modename)
                    else:
                        self.mode = NamedSize(geometry.size, name=modename)

            size = property(lambda self: NamedSize(
                Size(reversed(self.mode)), name=self.mode.name
            ) if self.rotation.is_odd else self.mode)
