# This Python file uses the following encoding: utf-8

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

import gettext
gettext.install('arandr')

__version__ = '0.1.9'
PROGRAMNAME = _(u'ARandR Screen Layout Editor')
## translators, please translate in the style of "Another XRandR GUI
## (ein weiteres GUI für XRandR)" so users get both the explanation of
## the acronym and a localized version.
PROGRAMDESCRIPTION = _(u'Another XRandR GUI')
COPYRIGHT = u'© chrysn 2008 – 2016, Себастьян Gli ţa Κατινα 2011, Johannes Holmberg 2015'

# other names of contributors found in the git history. mailmap (see
# git-shortlog(1)) won't cut it, because some contributors don't have any email
# address at all (or might want to be attributed without address).
COMMITTER_ALIASES = {
        'chrysn <chrysn@84c1553d-868a-485e-9ebb-c7de0e225ff1>': 'chrysn <chrysn@fsfe.org>',
        'Rax <r-a-x@launchpad>': 'Rax Garfield',
        'o-157 <Unknown>': 'o-157',
        'cdemoulins <clement@archivel.fr>': 'Clément Démoulins <clement@archivel.fr>',
        'sjb <gseba@users.sourceforge.net>': 'Себастьян Gli ţa Κατινα <gseba@users.sourceforge.net>',
        'Chandru <gundachandru@gmail.com>': 'gundachandru <gundachandru@gmail.com>',
        'Dimitris Giouroukis <digitalbckp@launchpad>': 'Dimitris Giouroukis',
        'Alir3z4 <agahia.com@gmail.com>': 'Alireza Savand <agahia.com@gmail.com>',
        'el_libre como el chaval <el.libre@gmail.com>': 'el_libre <el.libre@gmail.com>',
        'phantomx <megaphantomx@bol.com.br>': 'Phantom X <megaphantomx@bol.com.br>',
        }

TRANSLATORS_OVERRIDES = {
        # fixing stuff all over the place
        'chrysn <chrysn@fsfe.org>': ['de', 'en'],
        'Michal Čihař <michal@cihar.com>': ['cs'],
        # see 3b0b47b3665 / c1a7b7edad34
        'Mohammad Alhargan <malham1@gmail.com>': ['ar'],
        }

# everything below this line is updated semi-manually using `./setup.py update_translator_credits`

TRANSLATORS = [
        'Algimantas Margevičius <margevicius.algimantas@gmail.com>',
        'Alireza Savand <agahia.com@gmail.com>',
        'Bakr Al-Tamimi <Bakr.Tamimi@gmail.com>',
        'Balázs Úr <urbalazs@gmail.com>',
        'Belvar <glasbarg@gmail.com>',
        'Bruno_Patri <bruno.patri@gmail.com>',
        'Carezero <carezero@qq.com>',
        'ChuChangMing <82724824@qq.com>',
        'Clément Démoulins <clement@archivel.fr>',
        'Denis Jukni <deblenden8@gmail.com>',
        'Dimitris Giouroukis',
        'Efstathios Iosifidis <iefstathios@gmail.com>',
        'Fred Maranhão <fred.maranhao@gmail.com>',
        'Guilherme Souza Silva <g.szsilva@gmail.com>',
        'HsH <hsh@runtu.org>',
        'Igor <vmta@yahoo.com>',
        'Ingemar Karlsson <ingemar@ingk.se>',
        'Ivan Vantu5z <vantu5z@mail.ru>',
        'Joe Hansen <joedalton2@yahoo.dk>',
        'Kristjan Räts <kristjanrats@gmail.com>',
        'Lu Ca <lmelonimamo@yahoo.it>',
        'Luca Vetturi <io@lucavettu.com>',
        'Luis García Sevillano <floss.dev@gmail.com>',
        'Mantas Kriaučiūnas <mantas@akl.lt>',
        'Mehmet Gülmen <memetgulmen@gmail.com>',
        'Michal Čihař <michal@cihar.com>',
        'Miguel Anxo Bouzada <mbouzada@gmail.com>',
        'Mohammad Alhargan <malham1@gmail.com>',
        'Olexandr Nesterenko <olexn@ukr.net>',
        'ParkJS <HeavensBus@gmail.com>',
        'Phantom X <megaphantomx@bol.com.br>',
        'Piotr Strebski <strebski@o2.pl>',
        'Quizzlo <paolone.marco@gmail.com>',
        'Rax Garfield',
        'Ricardo A. Hermosilla Carrillo <ra.hermosillac@gmail.com>',
        'RooTer <rooter@kyberian.net>',
        'Sebastian Wahl <swahl11@student.aau.dk>',
        'Semsudin Abdic <abdic88@gmail.com>',
        'Slavko <linux@slavino.sk>',
        'Slobodan Simić <slsimic@gmail.com>',
        'Tamás Nagy <kisagy@gmail.com>',
        'Tuux <tuxa@galaxie.eu.org>',
        'Vladimir <vladimir-csp@yandex.ru>',
        'aboodilankaboot <shiningmoon25@gmail.com>',
        'agilob <weblate@agilob.net>',
        'cho bkwon <chobkwon@gmail.com>',
        'chrysn <chrysn@fsfe.org>',
        'el_libre <el.libre@gmail.com>',
        'gundachandru <gundachandru@gmail.com>',
        'ikmaak <info@ikmaak.nl>',
        'josep constanti <jconstanti@yahoo.es>',
        'o-157',
        'pCsOrI <pcsori@gmail.com>',
        'reza khan <reza_khn@yahoo.com>',
        'wimfeijen <wimfeijen@gmail.com>',
        'Себастьян Gli ţa Κατινα <gseba@users.sourceforge.net>'
        ]
