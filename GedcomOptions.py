#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2012       Doug Blank <doug.blank@gmail.com>
# Copyright (C) 2012       Bastien Jacquet
# Copyright (C) 2015       Kati Haapamaki <kati.haapamaki@gmail.com>
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

"""
(documentation ouf of date)

Modifies GedcomWriter to better suite used together with TNG

Places:
    Don't show address if there is nothing valuable in addition to place title
    If address is shown, add all the fields that can be extracted from place tree

    Optional: Try to generate missing coordinates from places above in place tree
    (currently only if places' titles match)

Names:
    (not implemented)
    Optional: Move patronymic surnames in the end of forenames

"""
#------------------------------------------------------------------------
#
# GTK modules
#
#------------------------------------------------------------------------
from __future__ import unicode_literals

from gi.repository import Gtk

from gramps.plugins.export import exportgedcom
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.lib import (AttributeType, ChildRefType, Citation, Date,
                            EventRoleType, EventType, LdsOrd, NameType,
                            PlaceType, NoteType, Person, UrlType,
                            SrcAttributeType, NameOriginType)

from gramps.gen.errors import DatabaseError
from gramps.gui.plug.export import WriterOptionBox
from gramps.gen.utils.place import conv_lat_lon
from gramps.gen.utils.location import get_main_location
from gramps.gen.display.place import displayer as place_displayer
from gramps.gen.lib.date import Today

__version__ = "0.4.1"

try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

class GedcomWriterExtension(exportgedcom.GedcomWriter):
    """
    GedcomWriter extension
    """
    _address_format = ["%street, %custom, %unknown, %building, %department, %farm, %neighborhood",
                       "%hamlet, %village, %borough, %locality",
                       "%code+-[%town, %city, %municipality], %parish",
                       "%district, %region, %province, %county, %state",
                       "%country",
                       ""]

    _def_address_format = ["%street",
                           "%locality",
                           "%city",
                           "%state",
                           "%country",
                           "%code"]


    _place_keys = ['street', 'department', 'building', 'farm', 'neighborhood', 'hamlet', 'village',
                   'borough', 'locality', 'town', 'city', 'municipality', 'parish', 'district',
                   'region', 'province', 'county', 'state', 'country', 'custom', 'unknown', 'code']

    _place_types = dict(street=PlaceType.STREET,
                       department=PlaceType.DEPARTMENT,
                       building=PlaceType.BUILDING,
                       farm=PlaceType.FARM,
                       neighborhood=PlaceType.NEIGHBORHOOD,
                       hamlet=PlaceType.HAMLET,
                       village=PlaceType.VILLAGE,
                       borough=PlaceType.BOROUGH,
                       locality=PlaceType.LOCALITY,
                       town=PlaceType.TOWN,
                       city=PlaceType.CITY,
                       municipality=PlaceType.MUNICIPALITY,
                       parish=PlaceType.PARISH,
                       district=PlaceType.DISTRICT,
                       province=PlaceType.PROVINCE,
                       region=PlaceType.REGION,
                       county=PlaceType.COUNTY,
                       state=PlaceType.STATE,
                       country=PlaceType.COUNTRY,
                       custom=PlaceType.CUSTOM,
                       unknown=PlaceType.UNKNOWN)

    # 'accuracy' of coordinates will be determined by place types which are groupped as:
    _address1_level_place_types = [PlaceType.STREET, PlaceType.DEPARTMENT, PlaceType.BUILDING,
                                   PlaceType.FARM, PlaceType.NEIGHBORHOOD, PlaceType.HAMLET]
    _address2_level_place_types = [PlaceType.VILLAGE, PlaceType.BOROUGH, PlaceType.LOCALITY]
    _city_level_place_types = [PlaceType.TOWN, PlaceType.MUNICIPALITY, PlaceType.CITY, PlaceType.PARISH]
    _county_level_place_types = [PlaceType.DISTRICT, PlaceType.COUNTY, PlaceType.REGION]
    _state_level_place_types = [PlaceType.STATE]
    _country_level_place_types = [PlaceType.COUNTRY]
    _unknown_level_place_types = [PlaceType.UNKNOWN, PlaceType.CUSTOM] # will be interpreted with highest accuracy

    #parser = FormatStringParser()

    def __init__(self, database, user, option_box=None):
        super(GedcomWriterExtension, self).__init__(database, user, option_box)
        if option_box:
            self.get_coordinates = option_box.get_coordinates
            self.export_only_useful_pe_addresses = option_box.export_only_useful_pe_addresses
            self.extended_pe_addresses = option_box.extended_pe_addresses
            self.avoid_repetition_in_pe_addresses = option_box.avoid_repetition_in_pe_addresses
            self.include_tng_place_levels = option_box.include_tng_place_levels
            self.omit_borough_from_address = option_box.omit_borough_from_address
            self.move_patronymics = option_box.move_patronymics
        else:
            self.get_coordinates = 1
            self.export_only_useful_pe_addresses = 1
            self.extended_pe_addresses = 1
            self.avoid_repetition_in_pe_addresses = 1
            self.include_tng_place_levels = 1
            self.omit_borough_from_address = 1
            self.move_patronymics = 1

        self.parser = FormatStringParser(self._place_keys)


    def _person_name(self, name, attr_nick):
        """
        n NAME <NAME_PERSONAL> {1:1}
        +1 NPFX <NAME_PIECE_PREFIX> {0:1}
        +1 GIVN <NAME_PIECE_GIVEN> {0:1}
        +1 NICK <NAME_PIECE_NICKNAME> {0:1}
        +1 SPFX <NAME_PIECE_SURNAME_PREFIX {0:1}
        +1 SURN <NAME_PIECE_SURNAME> {0:1}
        +1 NSFX <NAME_PIECE_SUFFIX> {0:1}
        +1 <<SOURCE_CITATION>> {0:M}
        +1 <<NOTE_STRUCTURE>> {0:M}
        """

        if not self.move_patronymics:
            super(GedcomWriterExtension, self)._person_name(name, attr_nick)
        else:
            firstname = name.get_first_name().strip()

            surns = []
            surprefs = []

            for surn in name.get_surname_list():
                if surn.get_origintype() == NameOriginType.PATRONYMIC \
                        or surn.get_origintype() == NameOriginType.MATRONYMIC:
                    firstname = firstname + " " + surn.get_surname().replace('/', '?')
                else:
                    surns.append(surn.get_surname().replace('/', '?'))

                    if surn.get_connector():
                        # we store connector with the surname
                        surns[-1] = surns[-1] + ' ' + surn.get_connector()
                    surprefs.append(surn.get_prefix().replace('/', '?'))
            surname = ', '.join(surns)
            surprefix = ', '.join(surprefs)
            suffix = name.get_suffix()
            title = name.get_title()
            nick = name.get_nick_name()
            if nick.strip() == '':
                nick = attr_nick

            #gedcom name
            gedcom_surname = name.get_surname().replace('/', '?')
            if suffix == "":
                gedcom_name = '%s /%s/' % (firstname, gedcom_surname)
            else:
                gedcom_name = '%s /%s/ %s' % (firstname, gedcom_surname, suffix)

            self._writeln(1, 'NAME', gedcom_name)
            if int(name.get_type()) == NameType.BIRTH:
                pass
            elif int(name.get_type()) == NameType.MARRIED:
                self._writeln(2, 'TYPE', 'married')
            elif int(name.get_type()) == NameType.AKA:
                self._writeln(2, 'TYPE', 'aka')
            else:
                self._writeln(2, 'TYPE', name.get_type().xml_str())

            if firstname:
                self._writeln(2, 'GIVN', firstname)
            if surprefix:
                self._writeln(2, 'SPFX', surprefix)
            if surname:
                self._writeln(2, 'SURN', surname)
            if name.get_suffix():
                self._writeln(2, 'NSFX', suffix)
            if name.get_title():
                self._writeln(2, 'NPFX', title)
            if nick:
                self._writeln(2, 'NICK', nick)

            self._source_references(name.get_citation_list(), 2)
        self._note_references(name.get_note_list(), 2)

    def _place(self, place, level):
        """
        PLACE_STRUCTURE:=
            n PLAC <PLACE_NAME> {1:1}
            +1 FORM <PLACE_HIERARCHY> {0:1}
            +1 FONE <PLACE_PHONETIC_VARIATION> {0:M}  # not used
            +2 TYPE <PHONETIC_TYPE> {1:1}
            +1 ROMN <PLACE_ROMANIZED_VARIATION> {0:M} # not used
            +2 TYPE <ROMANIZED_TYPE> {1:1}
            +1 MAP {0:1}
            +2 LATI <PLACE_LATITUDE> {1:1}
            +2 LONG <PLACE_LONGITUDE> {1:1}
            +1 <<NOTE_STRUCTURE>> {0:M}

        ADDRESS STRUCTURE;=
            n ADDR <ADDR1>
            +1 ADR1 <ADDR1>
            +1 ADR2 <ADDR2>
            +1 CITY <CITY>
            +1 STAE <STATE>
            +1 POST <POSTAL CODE>
            +1 CTRY <COUNTRY>

        Where
            ADDR1 = street, unknown, custom, department, building, farm, neighborhood
            ADDR2 = hamlet, village, borough, locality
            CITY = municipality, town, city, parish
            STATE = district, province, region, county, state
            COUNTRY = country
        """

        if place is None:
            return

        place_name = place_displayer.display(self.dbase, place)
        self._writeln(level, "PLAC", place_name.replace('\r', ' '), limit=120)
        longitude = place.get_longitude()
        latitude = place.get_latitude()
        title = place_name.replace('\r', ' ')

        # Get missing coordinates from place tree

        max_place_level_difference = 2

        place_level = self._tng_place_level(place)[0]
        zoom_level = self._tng_place_level(place)[1]

        if self.get_coordinates:

            test_tng_place_level = place_level
            inherited_place = None

            place_level_diff = 999

            if self.get_coordinates and not longitude and not latitude:
                place_list = self.get_place_list(place)
                if len(place_list) > 1:
                    for place_above in place_list:
                        if place is not place_above:
                            title_above = place_displayer.display(self.dbase, place_above).replace('\r', ' ')

                            test_longitude = place_above.get_longitude()
                            test_latitude = place_above.get_latitude()
                            if test_latitude and test_longitude:
                                test_tng_place_level = self._tng_place_level(place_above)[0]
                                test_place_level_diff = test_tng_place_level - place_level

                                # negative differences means the place is even more accurate
                                # (how to treat this?)
                                if test_place_level_diff < 0:
                                    test_place_level_diff = 0

                                if test_place_level_diff < place_level_diff \
                                        and test_place_level_diff <=  max_place_level_difference \
                                        or title == title_above:
                                    longitude = test_longitude
                                    latitude = test_latitude
                                    inherited_place = place_above
                                    place_level_diff = test_place_level_diff
                    if inherited_place:
                        place_level = self._tng_place_level(inherited_place)[0]
                        zoom_level = self._tng_place_level(inherited_place)[1]


        if longitude and latitude:
            (latitude, longitude) = conv_lat_lon(latitude, longitude, "GEDCOM")
        if longitude and latitude:
            self._writeln(level+1, "MAP")
            self._writeln(level+2, 'LATI', latitude)
            self._writeln(level+2, 'LONG', longitude)
            if self.include_tng_place_levels:
                self._writeln(level+2, 'PLEV', '%d' % place_level)
                self._writeln(level+2, 'ZOOM', '%d' % zoom_level)

        # The Gedcom standard shows that an optional address structure can
        # be written out in the event detail.
        # http://homepages.rootsweb.com/~pmcbride/gedcom/55gcch2.htm#EVENT_DETAIL


        title = place_name.replace('\r', ' ')
        location = get_main_location(self.dbase, place)
        postal_code = place.get_code()

        placetree = self.generate_place_dictionary(place)

        # Check if there is any piece of information in places that is not in place's title, and if is,
        # will add address data in gedcom

        if not self.export_only_useful_pe_addresses or self._is_extra_info_in_place_names(title, placetree):

            # Don't show borough, when street and city is present (more like modern address)
            if self.omit_borough_from_address and placetree['street'] and (placetree['city'] or placetree['town']):
                placetree['borough'] = ""

            # Generate Address field from all the place types given
            if self.extended_pe_addresses:
                #parser = FormatStringParser(self._place_keys)

                if self.avoid_repetition_in_pe_addresses:
                    self._remove_repetitive_places(placetree, self._address_format)

                address1 = self.parser.parse(placetree, self._address_format[0])
                address2 = self.parser.parse(placetree, self._address_format[1])
                city = self.parser.parse(placetree, self._address_format[2])
                state = self.parser.parse(placetree, self._address_format[3])
                country = self.parser.parse(placetree, self._address_format[4])
                postal_code = self.parser.parse(placetree, self._address_format[5])

            else:
                address1 = self.parser.parse(placetree, self._def_address_format[0])
                address2 = self.parser.parse(placetree, self._def_address_format[1])
                city = self.parser.parse(placetree, self._def_address_format[2])
                state = self.parser.parse(placetree, self._def_address_format[3])
                country = self.parser.parse(placetree, self._def_address_format[4])
                postal_code = self.parser.parse(placetree, self._def_address_format[5])

            # Write Address For the Place
            if address1 or address2 or state or postal_code:
                self._writeln(level, "ADDR", address1)
                if address1:
                    self._writeln(level + 1, 'ADR1', address1)
                if address2:
                    self._writeln(level + 1, 'ADR2', address2)
                if city:
                    self._writeln(level + 1, 'CITY', city)
                if state:
                    self._writeln(level + 1, 'STAE', state)
                if postal_code:
                    self._writeln(level + 1, 'POST', postal_code)
                if country:
                    self._writeln(level + 1, 'CTRY', country)

        self._note_references(place.get_note_list(), level+1)

    def generate_place_dictionary(self, place):
        db = self.dbstate.get_database()
        location = get_main_location(db, place)
        place_dict = dict()

        for key in self._place_keys:
            place_type = self._place_types.get(key.lower())
            if place_type:
                value = location.get(place_type)
            elif key == "code":
                value = place.get_code()
            else:
                value = ""
            if not value:
                value = ""

            place_dict[key] = value
        return place_dict

    def _remove_repetitive_places(self, place_dictionary, address_format):
        ret = None
        keys = dict()
        keys_to_remove = []

        for address_line in address_format:
            keys.update(self.parser.get_parsed_keys(place_dictionary, address_line))

        for key, value in keys.items():
            for check_key, check_value in keys.items():
                if key != check_key:
                    if value and check_value:
                        test = " " + value + " "
                        check_test = " " + check_value + " "
                        if test.find(check_test) >= 0:
                            keys_to_remove.append(check_key)
                            keys[check_key] = ""

        if len(keys_to_remove) == 0:
            return place_dictionary
        else:
            new_dict = place_dictionary.copy()
            for key in keys_to_remove:
                new_dict[key] = ""
            return new_dict


    def _is_extra_info_in_place_names(self, place_title, place_dictionary):
        """

        """
        ret = False
        if place_title:
            for key, place_name in place_dictionary.items():
                if place_name:
                    if place_title.find(place_name) < 0:
                        ret = True
                        break

        return ret

    def get_place_list(self, place, date=None):
        """
        Returns a list of all places in place tree
        """

        db = self.dbase

        if date is None:
            date = Today()
        visited = [place.handle]
        lines = [place]
        while True:
            handle = None
            for placeref in place.get_placeref_list():
                ref_date = placeref.get_date_object()
                if ref_date.is_empty() or date.match(ref_date):
                    handle = placeref.ref
            if handle is None or handle in visited:
                break
            place = db.get_place_from_handle(handle)
            if place is None:
                break
            visited.append(handle)
            lines.append(place)
        return lines

    def _tng_place_level(self, place):
        level = 6
        zoom = 9
        if place.get_type() in self._unknown_level_place_types:
            level, zoom = 1, 13
        if place.get_type() in self._address1_level_place_types:
            level, zoom = 1, 13
        if place.get_type() in self._address2_level_place_types:
            level, zoom = 2, 11
        if place.get_type() in self._city_level_place_types:
            level, zoom = 3, 9
        if place.get_type() in self._county_level_place_types:
            level, zoom = 4, 7
        if place.get_type() is PlaceType.STATE:
            level, zoom = 5, 5
        if place.get_type() is PlaceType.COUNTRY:
            level, zoom = 6, 4
        return level, zoom


#-------------------------------------------------------------------------
#
# GedcomWriter Options
#
#-------------------------------------------------------------------------
class GedcomWriterOptionBox(WriterOptionBox):
    """
    Create a VBox with the option widgets and define methods to retrieve
    the options.

    """
    def __init__(self, person, dbstate, uistate):
        """
        Initialize the local options.
        """
        super(GedcomWriterOptionBox, self).__init__(person, dbstate, uistate)
        self.get_coordinates = 1
        self.get_coordinates_check = None
        self.export_only_useful_pe_addresses = 1
        self.export_only_useful_pe_addresses_check = None
        self.extended_pe_addresses = 1
        self.extended_pe_addresses_check = None
        self.avoid_repetition_in_pe_addresses = 1
        self.avoid_repetition_in_pe_addresses_check = None
        self.include_tng_place_levels = 1
        self.include_tng_place_levels_check = None
        self.omit_borough_from_address = 1
        self.omit_borough_from_address_check = None
        self.move_patronymics = 1
        self.move_patronymics_check = None

    def get_option_box(self):
        option_box = super(GedcomWriterOptionBox, self).get_option_box()

        # Make options:
        self.export_only_useful_pe_addresses_check = \
            Gtk.CheckButton(_("Omit addresses that don't have any info in addition to place title"))
        self.extended_pe_addresses_check = \
            Gtk.CheckButton(_("Include all kind of place types in place event addresses (not only street/locality)"))
        self.avoid_repetition_in_pe_addresses_check = \
            Gtk.CheckButton(_("Try to avoid repetition in address fields (experimental)"))
        self.omit_borough_from_address_check = \
            Gtk.CheckButton(_("Omit neighborhood from addresses that have street and city (experimental)"))
        self.get_coordinates_check = \
            Gtk.CheckButton(_("Inherit missing coordinates from place tree"))
        self.include_tng_place_levels_check = \
            Gtk.CheckButton(_("Include TNG specific place level tags 'PLEV' and 'ZOOM'"))
        self.move_patronymics_check = \
            Gtk.CheckButton(_("Move matro-/patronynic surnames to forename"))

        # Set defaults:
        self.get_coordinates_check.set_active(1)
        self.export_only_useful_pe_addresses_check.set_active(1)
        self.extended_pe_addresses_check.set_active(1)
        self.avoid_repetition_in_pe_addresses_check.set_active(1)
        self.include_tng_place_levels_check.set_active(1)
        self.omit_borough_from_address_check.set_active(1)
        self.move_patronymics_check.set_active(1)

        # Add to gui:
        option_box.pack_start(self.move_patronymics_check, False, False, 0)
        option_box.pack_start(self.export_only_useful_pe_addresses_check, False, False, 0)
        option_box.pack_start(self.extended_pe_addresses_check, False, False, 0)
        option_box.pack_start(self.omit_borough_from_address_check, False, False, 0)
        option_box.pack_start(self.avoid_repetition_in_pe_addresses_check, False, False, 0)
        option_box.pack_start(self.get_coordinates_check, False, False, 0)
        option_box.pack_start(self.include_tng_place_levels_check, False, False, 0)

        # Return option box:
        return option_box

    def parse_options(self):
        """
        Get the options and store locally.
        """
        super(GedcomWriterOptionBox, self).parse_options()
        if self.get_coordinates_check:
            self.get_coordinates = self.get_coordinates_check.get_active()
        if self.export_only_useful_pe_addresses_check:
            self.export_only_useful_pe_addresses = self.export_only_useful_pe_addresses_check.get_active()
        if self.extended_pe_addresses_check:
            self.extended_pe_addresses = self.extended_pe_addresses_check.get_active()
        if self.avoid_repetition_in_pe_addresses_check:
            self.avoid_repetition_in_pe_addresses = self.avoid_repetition_in_pe_addresses_check.get_active()
        if self.include_tng_place_levels_check:
            self.include_tng_place_levels = self.include_tng_place_levels_check.get_active()
        if self.omit_borough_from_address_check:
            self.omit_borough_from_address = self.omit_borough_from_address_check.get_active()
        if self.move_patronymics_check:
            self.move_patronymics = self.move_patronymics_check.get_active()


def export_data(database, filename, user, option_box=None):
    """
    External interface used to register with the plugin system.
    """
    ret = False
    try:
        ged_write = GedcomWriterExtension(database, user, option_box)
        ret = ged_write.write_gedcom_file(filename)
    except IOError as msg:
        msg2 = _("Could not create %s") % filename
        user.notify_error(msg2, msg)
    except DatabaseError as msg:
        user.notify_db_error(_("Export failed"), msg)
    return ret



#!/usr/bin/python
#
# FORMAT STRING PARSER
#
# Parses format string with key coded values in dictionary removing unnecessary separators between parsed names
#
# (C) 2015  Kati Haapamaki
#
# ToDo:
# methods to change default enclosing chars




# =====================================================================================================
#
#   ELEMENT TYPE
#
# =====================================================================================================

class ElementType():
    KEY = 0
    SEPARATOR = 11
    PREFIX = 12
    SUFFIX = 13
    PARSED = -1
    PLAINTEXT = 1
    OPTIONOPERATOR = 21
    BINDOPERATOR = 22

# =====================================================================================================
#
#   CASE
#
# =====================================================================================================

class Case():
    NONE = 0
    UPPERCASE = 1
    LOWERCASE = 2
    SENTENCECASE = 3
    TITLECASE = 4
    SENTENCECASENUMSKIP = 5
    TITLECASESPACEREQUIRED = 6

    @staticmethod
    def convert_case(string, case):
        """

        :param string:
        :param case:
        :return:
        """
        if not string:
            return ""

        if case == Case.UPPERCASE:
            return string.upper()
        elif case == Case.LOWERCASE:
            return string.lower()
        elif case == Case.SENTENCECASE or case == Case.SENTENCECASENUMSKIP:
            pos = Case.find_first_alphanum(string) if case == Case.SENTENCECASE else Case.find_first_alpha(string)
            if pos >= 0:
                before = string[:pos] if pos > 0 else ""
                after = string[pos+1:] if len(string) > pos + 1 else ""
                return before + string[pos].upper() + after
            else:
                return string
        elif case == Case.TITLECASE or case == Case.TITLECASESPACEREQUIRED:
            prev_c = " "
            new_string = ""
            for c in string:
                if not prev_c.isalnum() and case == Case.TITLECASE\
                        or prev_c == " " and case == Case.TITLECASESPACEREQUIRED:
                    new_string = new_string + c.upper()
                else:
                    new_string = new_string + c
                prev_c = c
            return new_string
        else:
            return string

    @staticmethod
    def convert_element_case(element):
        if element.case != Case.NONE and element.value:
            element.value = Case.convert_case(element.value, element.case)
            element.case = Case.NONE

    @staticmethod
    def find_first_alphanum(string):
        index = 0
        if not string:
            return -1
        for c in string:
            if c.isalnum():
                return index
            index += 1
        return -1

    @staticmethod
    def find_first_alpha(string):
        index = 0
        if not string:
            return -1
        for c in string:
            if c.isalpha():
                return index
            index += 1
        return -1

    @staticmethod
    def get_case(string):
        cases = [Case.LOWERCASE, Case.UPPERCASE, Case.TITLECASE, Case.TITLECASESPACEREQUIRED,
                 Case.SENTENCECASE, Case.SENTENCECASENUMSKIP]
        for case in cases:
            if string == Case.convert_case(string, case):
                return case
        return Case.NONE

    @staticmethod
    def set_case_by_key_formatting(element):
        if not element:
            return
        if element.key != element.formatted_key:
            element.case = Case.get_case(element.formatted_key)
        return


# =====================================================================================================
#
#   PARSE MODE
#
# =====================================================================================================

class ParseMode():
    ALWAYS = 0
    IFANY = 1
    IFALL = 2


# =====================================================================================================
#
#   FORMAT STRING ELEMENT
#
# =====================================================================================================

class FormatStringElement():
    type = ElementType.PLAINTEXT
    key = None
    formatted_key = None
    case = Case.NONE
    value = ""
    parsed = False
    parsed_values = dict()

    def __init__(self, contents, element_type, case=Case.NONE, value=""):
        if element_type == ElementType.KEY:
            self.key = contents
            self.value = value
            if value:
                self.parsed = True
        else:
            self.value = contents
        self.type = element_type
        self.case = case

    def convert_case(self, case=None):
        if not case:
            case = self.case
        if case != Case.NONE and self.value:
            self.value = Case.convert_case(self.value, case)
            self.case = Case.NONE

    def print_element(self):  # for debugging
        s = '"' + self.value + '" '
        s += str(self.type) + ", " + str(self.case)
        if self.key:
            s += " [" + self.key + "]"
        print(s)

# =====================================================================================================
#
#   FORMAT STRING PARSER
#
# =====================================================================================================

class FormatStringParser():
    """

    """

# -----------------------------------------------------------------------------------------------------
#   INIT
#
# -----------------------------------------------------------------------------------------------------

    _all_keys = []

    _key_prefix = "%"
    _enc_any_start = '['
    _enc_any_end = ']'
    _enc_all_start = '<'
    _enc_all_end = '>'
    _enc_always_start = '{'
    _enc_always_end = '}'
    _escape_char = "\\"
    _optional_operator = '|'
    _bind_right_operator = '-+'
    _bind_left_operator = '+-'
    _uppercase_operator = "$u"
    _lowercase_operator = "$l"
    _sentencecase_operator = "$s"
    _titlecase_operator = "$t"
    _sentencecase_numskip_operator = "$1"
    _titlecasenumskip_operator = "$2"

    case_operators = dict(
        uppercase="$u",
        lowercase="$l",
        sentencecase="$s"
        # an unfinished idea...
    )

    def __init__(self, key_list=None):
        if not key_list:
            self._all_keys = []
        else:
            self.set_keys(key_list)

    def set_keys(self, key_list):
        """

        :param key_list:
        :return:
        """
        self._all_keys = []
        if type(key_list) is list:
            self._all_keys = key_list
        elif type(key_list) is dict:
            for key, value in key_list.items():
                self._all_keys.append(key)
        else:
            raise TypeError("Incorrect key list type")

    def append_keys(self, key_list):
        """

        :param key_list:
        :return:
        """
        if type(key_list) is list:
            self._all_keys.append(key_list)
        elif type(key_list) is dict:
            for key, value in key_list.items():
                if not self._has_item(key, self._all_keys):
                    self._all_keys.append(key)

# -----------------------------------------------------------------------------------------------------
#   PARSE
#
# -----------------------------------------------------------------------------------------------------

    def parse(self, values, format_string):
        """
        The main method to get work done. Call it from outside class.

        :param values:          The dictionary including all keywords to be replaced in the format string
        :param format_string:   The format string to be parsed
        :return:                Parsed string
        """

        self.append_keys(values)
        parsed_list = self._recurse_enclosures_and_parse(values, format_string)

        # collect remaining elements
        parsed_list = self._collect(parsed_list)

        if len(parsed_list) > 0:
            passed_keys = parsed_list[0].parsed_values
            #print(passed_keys)

        return self._make_string_from_list(parsed_list)

    def get_parsed_keys(self, values, format_string):

        self.append_keys(values)
        parsed_list = self._recurse_enclosures_and_parse(values, format_string)
        parsed_list = self._collect(parsed_list)

        if len(parsed_list) > 0:
            passed_keys = parsed_list[0].parsed_values
            return passed_keys

        return dict()

    def _recurse_enclosures_and_parse(self, values, format_string, mode=ParseMode.IFANY, case=Case.NONE):
        """
        Recurses format string's enclosed parts, and parses them into tuple list.
        Returns tuple list of elements of partial format string when going through recursion
        Finally returns tuple list that is suppressed to single item including the full parsed string

        :param values:
        :param format_string:
        :param mode:
        :return:
        """
        new_case = Case.NONE
        if format_string:
                c = format_string[0:2]
                if c == self._uppercase_operator:
                    new_case = Case.UPPERCASE
                elif c == self._sentencecase_operator:
                    new_case = Case.SENTENCECASE
                elif c == self._sentencecase_numskip_operator:
                    new_case = Case.SENTENCECASENUMSKIP
                elif c == self._titlecase_operator:
                    new_case = Case.TITLECASE
                elif c == self._titlecasenumskip_operator:
                    new_case = Case.TITLECASESPACEREQUIRED
                elif c == self._lowercase_operator:
                    new_case = Case.LOWERCASE
                if new_case != Case.NONE:
                    format_string = format_string[2:]
                    case = new_case

        if case == Case.SENTENCECASENUMSKIP or case == Case.SENTENCECASE:
            sentence_case = case
            case = Case.NONE
        else:
            sentence_case = case

        enclosing_start = self._find_enclosing_start(format_string)
        if enclosing_start:
            start_pos = enclosing_start[0]

            if start_pos >= 0:
                enclosing_end = self._find_enclosing_end(format_string, enclosing_start)
                if enclosing_end:
                    end_pos = enclosing_end[0]
                    enclosed_mode = enclosing_end[1]
                    # Divide in parts. Middle is part that is enclosed with brackets, 'before' and 'after' are around it
                    before = format_string[:start_pos] if start_pos > 0 else ""
                    middle = format_string[start_pos + 1:end_pos] if end_pos - start_pos >= 2 else ""
                    after = format_string[end_pos + 1:] if end_pos < len(format_string) - 1 else ""

                    #print("//" + before + "//" + middle + "//" + after + "//")
                    recursion = self._recurse_enclosures_and_parse(values, before, mode, sentence_case) \
                        + self._collect(self._recurse_enclosures_and_parse(values, middle, enclosed_mode, case),
                                        enclosed_mode) \
                        + self._recurse_enclosures_and_parse(values, after, mode, case)

                    return recursion

        new_list = self._split_and_parse(values, format_string, sentence_case)

        return new_list

    def _split_and_parse(self, values, format_string, case=Case.NONE):
        """
        Splits format string into tuple list, and then parses keys included in it


        :param values:          Values to be parsed in key/value dictionary
        :param format_string:   The format string to be parsed
        :return:                The format string splitted into elements in a list containing tuples
        """
        element_list = self._split_format_string(format_string, case)
        self._parse_keys(element_list, values, case)
        return element_list

    def _split_format_string(self, format_string, case=Case.NONE):
        """
        Splits format string into list of elements

        :param format_string:   The format string to be parsed
        :return:                The format string splitted into elements in a list containing tuples


        Tuples has format:
            ((key as string, formatted key as string), item type as ElementType, case as Case) ...for key element
                or
            (item as string, item type as ElementType, case as Case) ...for separators, operators and parsed keys

        case is for case conversion, and it will be passed along to be able to make case conversion at correct point

        """
        new_list = []
        remainder = format_string
        any_key_found = False
        if remainder:
            while remainder:
                next_key = self._get_next_key(remainder)
                if next_key:
                    actual_key = next_key[0]
                    formatted_key = next_key[1]
                    before, temp, after = remainder.partition(self._key_prefix + formatted_key)
                    if before:
                        if before == self._optional_operator:
                            element = FormatStringElement(before, ElementType.OPTIONOPERATOR, case)
                        elif before == self._bind_right_operator or before == self._bind_left_operator:
                            element = FormatStringElement(before, ElementType.BINDOPERATOR, case)
                        else:
                            if any_key_found:
                                element = FormatStringElement(before, ElementType.SEPARATOR, case)
                            else:
                                element = FormatStringElement(before, ElementType.PREFIX, case)

                        new_list.append(element)
                    new_key_element = FormatStringElement(actual_key, ElementType.KEY, case)
                    new_key_element.formatted_key = formatted_key
                    Case.set_case_by_key_formatting(new_key_element)
                    new_list.append(new_key_element)
                    any_key_found = True
                    remainder = after
                else:
                    if remainder == self._optional_operator:
                        element = FormatStringElement(remainder, ElementType.OPTIONOPERATOR, case)
                    elif remainder == self._bind_right_operator or remainder == self._bind_left_operator:
                        element = FormatStringElement(remainder, ElementType.BINDOPERATOR, case)
                    else:
                        if any_key_found:
                            element = FormatStringElement(remainder, ElementType.SUFFIX, case)
                        else:
                            element = FormatStringElement(remainder, ElementType.PLAINTEXT, case)

                    new_list.append(element)
                    remainder = ""

        return new_list

    def _parse_keys(self, element_list, values, inherited_case=Case.NONE):
        """
        Parses all the keys in the tuple list by using values given in key/value dictionary
        Also does case conversion if needed, but not the sentence case conversion, because that cannot be done yet

        :param values:
        :param element_list:
        :param inherited_case:
        :return:
        """
        if len(element_list) < 1:
            return

        for element in element_list:
            if element.case == Case.NONE:
                case = inherited_case
            else:
                case = element.case

            if element.type is ElementType.KEY:
                value = values.get(element.key)
                if not value:
                    value = ""
                element.value = value
                element.parsed = True

            if not (case == Case.SENTENCECASE or case == Case.SENTENCECASENUMSKIP):
                element.convert_case()

        return


    def _get_next_key(self, format_string):
        """
        Searches for the first key in a format string

        Search is case-insensitive and because of that, the method returns a tuple of which first item is
        the key in format that it is appears in the key list, and the second item is the key in format it
        appears in the format string

        If no key is found, the method returns None

        :param format_string:   The format string
        :return:                A tuple of the next key and its formatted version
        """
        any_found = False
        lowest_index = -1
        found_formatted_key = ""
        found_true_key = ""
        check_string = format_string.lower()

        if format_string:
            for key in self._all_keys:
                check_key = self._key_prefix + key.lower()
                found_pos = check_string.find(check_key, 0)
                if found_pos >= 0 and (found_pos < lowest_index or not any_found):
                    char_before = format_string[found_pos-1] if found_pos > 0 else ""
                    if char_before != self._escape_char:
                        lowest_index = found_pos
                        any_found = True
                        found_true_key = key
                        found_formatted_key = format_string[lowest_index:lowest_index+len(check_key)]
        if any_found:
            return found_true_key, found_formatted_key[len(self._key_prefix):]
        else:
            return None

# -----------------------------------------------------------------------------------------------------
#   COLLECT / SUPPRESS
#
# -----------------------------------------------------------------------------------------------------

    def _collect(self, element_list, mode=ParseMode.IFANY, case=Case.NONE):
        """
        One of they key methods. Suppresses a tuple list to length of 1 by processing all operators and
        disregarding empty parsed strings and separators between them

        :param element_list:  A tuple list
        :return:            A tuple list with single item
        """
        string_list = []
        index = 0
        any_parsed = False
        parsed_keys = dict()


        # change prefix and suffixes to separators if they are no longer in the beginning or in the end
        element_list = self._fix_separators(element_list)

        # process optional and binding operators
        element_list = self._handle_operators(element_list)

        first_item_case = Case.NONE  # will be used if there is need to make case conversion to sentence case

        for element in element_list:
            if index == 0:
                first_item_case = element.case # will be used for the whole string if sentence case...

            if element.parsed:
                any_parsed = True

            if element.type == ElementType.PARSED:
                 parsed_keys.update(element.parsed_values)

            if (element.parsed or element.type == ElementType.PLAINTEXT) and element.value:
                string_list.append(element.value)
                if element.type == ElementType.KEY:
                    parsed_keys[element.key] = element.value

                separator1 = separator2 = None
                found_more = False

                if len(element_list) > index + 2:
                    if element_list[index+1].type == ElementType.SEPARATOR:
                        separator1 = element_list[index + 1]
                    index2 = index + 1

                    # look for the next parsed value to determine what separators to use
                    for element2 in element_list[index+1:]:
                        if (element2.parsed or element2.type == ElementType.PLAINTEXT) and element2.value:
                            found_more = True
                            if index2 > index + 2 and element_list[index2 - 1].type == ElementType.SEPARATOR:
                                separator2 = element_list[index2 - 1]
                            break
                        index2 += 1

                    separator = separator1 if separator1 else separator2  # prefer using first separator, if two exists

                    if separator and found_more:
                        string_list.append(separator.value)


            elif element.type == ElementType.SEPARATOR:
                pass

            elif element.type == ElementType.PREFIX or element.type == ElementType.SUFFIX:
                string_list.append(element.value)

            index += 1

        parsed_items = self._number_of_non_empty_parsed_item(element_list)
        empty_items = self._number_of_empty_parsed_item(element_list)

        if mode == ParseMode.IFANY and parsed_items > 0 \
                or mode == ParseMode.ALWAYS \
                or mode == ParseMode.IFALL and parsed_items > 0 and empty_items == 0:

            parsed_string = "".join(string_list)

            if parsed_string:
                if parsed_string.find(self._escape_char) >= 0:
                    parsed_string = self._handle_escape_char(parsed_string)
                # execute sentence case conversion here - later than other conversions,
                # because we need completely parsed string to do that
                if first_item_case == Case.SENTENCECASE or first_item_case == Case.SENTENCECASENUMSKIP:
                   parsed_string = Case.convert_case(parsed_string, first_item_case)
        else:
            parsed_string = ""
            parsed_keys = dict()

        if any_parsed:
            collected_element = FormatStringElement(parsed_string, ElementType.PARSED, case, value=parsed_string)
            collected_element.parsed_values = parsed_keys
            collected_element.parsed = True
        else:
            collected_element = FormatStringElement(parsed_string, ElementType.PLAINTEXT, case)
        return [collected_element]

    def _fix_separators(self, element_list):
        """
        Should be used to convert suffixes and prefixes that origin from enclosed parts of format string
        into separators. Must be done before collect/suppress. Working ok?

        :param element_list:
        :return:
        """
        index = 0
        new_element_list = []
        for element in element_list:
            if index > 0 and index < len(element_list) - 1 \
                    and (element.type == ElementType.PREFIX or element.type == ElementType.SUFFIX):
                element.type = ElementType.SEPARATOR
            new_element_list.append(element)
            index += 1
        return new_element_list

    def _handle_operators(self, element_list):
        skip_next = False
        index = 0
        new_element_list = []
        prev_element = None

        for element in element_list:
            skip_this = False
            if not skip_next:
                if index > 0 and index < len(element_list) - 1 and prev_element:
                    next_element = element_list[index+1]
                    if element.type == ElementType.OPTIONOPERATOR:
                        if prev_element.parsed and next_element.parsed:
                            if not prev_element.value:
                                del new_element_list[-1]  # if prev item empty, delete along operator
                                skip_this = True
                            else:
                                skip_next = skip_this = True    # or else omit next, along operator
                    elif element.type == ElementType.BINDOPERATOR:
                        if element.value == self._bind_right_operator:
                            if index > 0 and index < len(element_list) - 1 \
                                    and not prev_element.value \
                                    and prev_element.parsed \
                                    and next_element.parsed:
                                skip_next = skip_this = True # delete next
                        if element.value == self._bind_left_operator:
                            if index > 0 and index < len(element_list) - 1 \
                                    and not next_element.value \
                                    and prev_element.parsed \
                                    and next_element.parsed:
                                del new_element_list[-1] # delete previous
                                skip_this = True
                if not skip_this:
                        new_element_list.append(element)
                        prev_element = element
            else:
                skip_next = False

            index += 1

        return new_element_list

# -----------------------------------------------------------------------------------------------------
#   MISC
#
# -----------------------------------------------------------------------------------------------------

    @staticmethod
    def _has_item(item, list_):
        """

        :param item:
        :param list_:
        :return:
        """
        for item_in_list in list_:
            if item == item_in_list:
                return True
        return False

    @staticmethod
    def _make_string_from_list(element_list):
        str_list = []

        for element in element_list:
            str_list.append(element.value)

        if str_list:
            return "".join(str_list)
        else:
            return ""

    def _handle_escape_char(self, string):
        index = 0
        new_string = []
        while index < len(string):
            if string[index] == self._escape_char:
                if index < len(string) - 1:
                    if string[index+1] != self._escape_char:
                        pass
                    else:
                        new_string.append(string[index])
                else:
                    pass
            else:
                new_string.append(string[index])
            index += 1
        return "".join(new_string)

    def _number_of_empty_parsed_item(self, element_list):
        """

        :param element_list:
        :return:
        """
        counter = 0
        for element in element_list:
            if element.parsed and not element.value:
                counter += 1
        return counter

    @staticmethod
    def _number_of_non_empty_parsed_item(element_list):
        """

        :param element_list:
        :return:
        """
        counter = 0
        for element in element_list:
            if element.parsed and element.value:
                counter += 1
        return counter

    def _find_enclosing_start(self, format_string, start_pos=0):
        """

        :param format_string:
        :param start_pos:
        :return:
        """
        index = start_pos
        found_enclosing = None
        for c in format_string[start_pos:]:
            if c == self._enc_any_start:
                found_enclosing = index, ParseMode.IFANY
            elif c == self._enc_all_start:
                found_enclosing = index, ParseMode.IFALL
            elif c == self._enc_always_start:
                found_enclosing = index, ParseMode.ALWAYS
            if found_enclosing:
                if index > start_pos:
                    if format_string[index-1] == self._escape_char:
                        found_enclosing = None # omit found enclosing if it's followed by escape char
                    else:
                        break
                else:
                    break

            index += 1

        return found_enclosing

    def _find_enclosing_end(self, format_string, enclosing_start):
        """

        :param format_string:
        :param enclosing_start:
        :return:
        """
        start_pos = enclosing_start[0] + 1
        found_enclosing_end = None

        if len(format_string)- start_pos > 1:

            mode = enclosing_start[1]
            if mode == ParseMode.IFALL:
                ec_end_char = self._enc_all_end
                ec_start_char = self._enc_all_start
            elif mode == ParseMode.ALWAYS:
                ec_end_char = self._enc_always_end
                ec_start_char = self._enc_always_start
            else:
                ec_end_char = self._enc_any_end
                ec_start_char = self._enc_any_start

            index = start_pos
            level = 0
            for c in format_string[start_pos:]:
                if c == ec_end_char:
                    if level == 0 and c == ec_end_char:
                        found_enclosing_end = index, mode
                        break
                    else:
                        level -= 1
                        if index > start_pos:
                            if format_string[index-1] == self._escape_char:
                                level += 1 # was escape, step back
                elif c == ec_start_char:
                    level += 1
                    if index > start_pos:
                        if format_string[index-1] == self._escape_char:
                            level -= 1 # was escape, step back

                index += 1

        return found_enclosing_end

    def _is_enclosing_start_char(self, c):
        """

        :param c:
        :return:
        """
        if not c:
            return False
        return c == self._enc_all_start or c == self._enc_any_start or c == self._enc_always_start

    def _is_enclosing_end_char(self, c):
        if not c:
            return False
        return c == self._enc_all_end or c == self._enc_any_end or c == self._enc_always_end

    def _is_enclosing_char(self, c):
        return self._is_enclosing_start_char(c) or self._is_enclosing_end_char(c)

    @staticmethod
    def _print_elements(element_list):
        for element in element_list:
            element.print_element()
