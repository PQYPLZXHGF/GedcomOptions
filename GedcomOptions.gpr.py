#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2012 Doug Blank <doug.blank@gmail.com>
# Copyright (C) 2015 Kati Haapamaki <kati.haapamaki@gmail.com>
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
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

# $Id: $

#------------------------------------------------------------------------
#
# Modified the GEDCOM Export for TNG -alpha
#
#------------------------------------------------------------------------

register(EXPORT,
    id    = 'GEDCOM Options',
    name  = _("GEDCOM Options"),
    name_accell  = _("GEDCOM Options (Expansion to default GedCom Export Module)"),
    description =  _("GEDCOM Options offers some customization to default export module."),
    version = '0.4.1',
    gramps_target_version = '4.1',
    status = UNSTABLE,
    fname = 'GedcomOptions.py',
    export_function = 'export_data',
    export_options = 'GedcomWriterOptionBox',
    export_options_title = _('GEDCOM Options'),
    extension = "ged",
)

