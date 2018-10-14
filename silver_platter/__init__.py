#!/usr/bin/python
# Copyright (C) 2018 Jelmer Vernooij
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

# TODO(jelmer): Imports with side-effects are bad...

import os
import sys

if os.name == "posix":
    import locale
    locale.setlocale(locale.LC_ALL, '')
    # Use better default than ascii with posix filesystems that deal in bytes
    # natively even when the C locale or no locale at all is given. Note that
    # we need an immortal string for the hack, hence the lack of a hyphen.
    sys._brz_default_fs_enc = "utf8"

import breezy
breezy.initialize()
import breezy.git  # For git support
import breezy.bzr  # For bzr support
import breezy.plugins.launchpad  # For lp: URL support
import breezy.plugins.debian  # For apt: URL support
