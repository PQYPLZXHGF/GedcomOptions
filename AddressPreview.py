# *-* coding: utf-8 *-*
from __future__ import unicode_literals

from gi.repository import Gtk

from gramps.gen.plug import Gramplet
from gramps.gui.widgets import Photo
from gramps.gen.const import GRAMPS_LOCALE as glocale

from gramps.gen.utils.place import conv_lat_lon
from gramps.gen.utils.file import media_path_full
from gramps.gen.display.place import displayer as place_displayer
from gi.repository import Gtk
from gi.repository import Pango
from gramps.gen.lib import PlaceType
from gramps.gen.lib import Place
from gramps.gen.utils.location import get_main_location
from gramps.gui.dbguielement import DbGUIElement
from gramps.gen.lib.date import Today

__version__ = "0.2.4"

try:
    trans = glocale.get_addon_translator(__file__)
except ValueError:
    trans = glocale.translation
_ = trans.gettext


class AddressPreview(Gramplet, DbGUIElement):
    """
    Displays the participants of an event.
    """
    def __init__(self, gui, nav_group=0):
        Gramplet.__init__(self, gui, nav_group)
        DbGUIElement.__init__(self, self.dbstate.db)
        self.parser = FormatStringParser(self._place_keys)

    def _connect_db_signals(self):
        """
        called on init of DbGUIElement, connect to db as required.
        """
        self.callman.register_callbacks({'place-update': self.changed,
                                         'event-update': self.changed})
        self.callman.connect_all(keys=['place', 'event'])
        #self.dbstate.db.connect('person-update', self.update)
        self.connect_signal('Place', self.update)

    def changed(self, handle):
        """
        Called when a registered person is updated.
        """
        self.update()

    def init(self):
        self.gui.WIDGET = self.build_gui()
        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add_with_viewport(self.gui.WIDGET)
        self.gui.WIDGET.show()

    def build_gui(self):
        """
        Build the GUI interface.
        """
        self.top = Gtk.HBox()
        vbox = Gtk.VBox()
        self.photo = Photo(self.uistate.screen_height() < 1000)
        self.title = Gtk.Label()
        self.title.set_alignment(0, 0)
        self.title.modify_font(Pango.FontDescription('sans bold 12'))
        vbox.pack_start(self.title, False, True, 7)
        self.table = Gtk.Table(n_rows=1, n_columns=2)
        vbox.pack_start(self.table, False, True, 0)
        self.top.pack_start(self.photo, False, True, 5)
        self.top.pack_start(vbox, False, True, 10)
        self.top.show_all()
        return self.top

# ------------------------------------------------------------------------------------------

    _address_format = ["%street, %custom, %unknown, %building, %department, %farm, %neighborhood",
                       "%hamlet, %village, %borough, %locality",
                       "[%CODE ]+-[%town, %city, %municipality], %parish",
                       "%district, %region, %province, %county, %state",
                       "%country",
                       ""]

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

    def add_row(self, title, value):
        """
        Add a row to the table.
        """
        label = Gtk.Label(label=title + ':')
        label.set_alignment(1, 0)
        label.show()
        value = Gtk.Label(label=value)
        value.set_alignment(0, 0)
        value.show()
        rows = self.table.get_property('n-rows')
        rows += 1
        self.table.resize(rows, 2)
        self.table.attach(label, 0, 1, rows, rows + 1, xoptions=Gtk.AttachOptions.FILL,
                                                       xpadding=10)
        self.table.attach(value, 1, 2, rows, rows + 1)

    def clear_table(self):
        """
        Remove all the rows from the table.
        """
        list(map(self.table.remove, self.table.get_children()))
        self.table.resize(1, 2)

    def db_changed(self):
        self.dbstate.db.connect('place-update', self.update)
        self.connect_signal('Place', self.update)

    def update_has_data(self):
        active_handle = self.get_active('Person')
        if active_handle:
            active_person = self.dbstate.db.get_person_from_handle(active_handle)
            self.set_has_data(active_person is not None)
        else:
            self.set_has_data(False)

    def main(self):
        self.display_empty()
        active_handle = self.get_active('Place')
        if active_handle:
            place = self.dbstate.db.get_place_from_handle(active_handle)
            self.top.hide()
            if place:
                self.display_place(place)
                self.set_has_data(True)
            else:
                self.set_has_data(False)
            self.top.show()
        else:
            self.set_has_data(False)

    def display_place(self, place):
        """
        Display details of the active place.
        """
        self.load_place_image(place)
        title = place_displayer.display(self.dbstate.db, place)
        self.title.set_text(title)
        self.clear_table()

        #parser = FormatStringParser(self._place_keys)
        place_dict = self.generate_place_dictionary(place)
        parser = FormatStringParser(place_dict)
        placetree = self.generate_place_dictionary(place)

        omitted = self._remove_repetitive_places(place_dict, self._address_format)
        if placetree['street'] and (placetree['city'] or placetree['town']):
                placetree['borough'] = ""
                omitted = omitted + ", " + placetree['borough'] if omitted else placetree['borough']

        addr1 = parser.parse(place_dict, self._address_format[0])
        addr2 = parser.parse(place_dict, self._address_format[1])
        city = parser.parse(place_dict, self._address_format[2])
        state = parser.parse(place_dict, self._address_format[3])
        country = parser.parse(place_dict, self._address_format[4])
        code = parser.parse(place_dict, self._address_format[5])

        if not self._is_extra_info_in_place_names(title, placetree):
            self.add_row(_("WILL NOT SHOW"), "")
        self.add_row(_("Address 1"), addr1)
        self.add_row(_("Address 2"), addr2)
        self.add_row(_("City"), city)
        self.add_row(_("State"), state)
        self.add_row(_("Country"), country)
        self.add_row(_("Postal Code"), code)
        if omitted:
            self.add_row(_(""), "")
            self.add_row(_("Omitted"), omitted)
        self.add_row(_(""), "")
        self.add_row(_("Version"), __version__)

        #self.add_row(_('Name'), place.get_name())
        #self.add_row(_('Type'), place.get_type())
        #self.display_separator()
        #self.display_alt_names(place)
        #self.display_separator()
        lat, lon = conv_lat_lon(place.get_latitude(),
                                place.get_longitude(),
                                format='DEG')
        if lat:
            self.add_row(_('Latitude'), lat)
        if lon:
            self.add_row(_('Longitude'), lon)

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
            if not value: value = ""

            place_dict[key] = value
        return place_dict

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

    def display_alt_names(self, place):
        """
        Display alternative names for the place.
        """
        alt_names = place .get_alternative_names()
        if len(alt_names) > 0:
            self.add_row(_('Alternative Names'), '\n'.join(alt_names))

    def display_empty(self):
        """
        Display empty details when no repository is selected.
        """
        self.photo.set_image(None)
        self.photo.set_uistate(None, None)
        self.title.set_text('')
        self.clear_table()

    def display_separator(self):
        """
        Display an empty row to separate groupd of entries.
        """
        label = Gtk.Label(label='')
        label.modify_font(Pango.FontDescription('sans 4'))
        label.show()
        rows = self.table.get_property('n-rows')
        rows += 1
        self.table.resize(rows, 2)
        self.table.attach(label, 0, 1, rows, rows + 1, xoptions=Gtk.AttachOptions.FILL)

    def load_place_image(self, place):
        """
        Load the primary image if it exists.
        """
        media_list = place.get_media_list()
        if media_list:
            media_ref = media_list[0]
            object_handle = media_ref.get_reference_handle()
            obj = self.dbstate.db.get_object_from_handle(object_handle)
            full_path = media_path_full(self.dbstate.db, obj.get_path())
            mime_type = obj.get_mime_type()
            if mime_type and mime_type.startswith("image"):
                self.photo.set_image(full_path, mime_type,
                                     media_ref.get_rectangle())
                self.photo.set_uistate(self.uistate, object_handle)
            else:
                self.photo.set_image(None)
                self.photo.set_uistate(None, None)
        else:
            self.photo.set_image(None)
            self.photo.set_uistate(None, None)

    def _remove_repetitive_places(self, place_dictionary, address_format):
        keys = dict()
        keys_to_remove = []

        for address_line in address_format:
            keys.update(self.parser.get_parsed_keys(place_dictionary, address_line))

        for key, value in keys.items():
            if key not in keys_to_remove:
                for check_key, check_value in keys.items():
                    if value == check_value and key != check_key:
                        print(key + " is same as " + check_key)
                    if key != check_key:
                        if value and check_value:
                            test = " " + value + " "
                            check_test = " " + check_value + " "
                            if test.find(check_test) >= 0:
                                keys_to_remove.append(check_key)
                                keys[check_key] = ""

        if len(keys_to_remove) == 0:
            return ""
        else:
            omit_string = ""

            for key in keys_to_remove:
                omit_string = place_dictionary[key] if not omit_string else omit_string + ", " + place_dictionary[key]
                place_dictionary[key] = ""
            return omit_string

# ===================================================================================================================
#
# FORMAT STRING PARSER 0.9.4
#
# Parses format string with key coded values in dictionary removing unnecessary separators between parsed names
#
# (C) 2015  Kati Haapamaki
#


#------------------------------------------------------------
#
#   ELEMENT TYPE
#
#------------------------------------------------------------

class ElementType():
    KEY = 0
    SEPARATOR = 11
    PREFIX = 12
    SUFFIX = 13
    PARSED = -1
    PLAINTEXT = 1
    OPTIONOPERATOR = 21
    BINDOPERATOR = 22

#------------------------------------------------------------
#
#   CASE
#
#------------------------------------------------------------

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


#------------------------------------------------------------
#
#   PARSE MODE
#
#------------------------------------------------------------

class ParseMode():
    ALWAYS = 0
    IFANY = 1
    IFALL = 2


#------------------------------------------------------------
#
#   FORMAT STRING ELEMENT
#
#------------------------------------------------------------

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

#------------------------------------------------------------
#
#   FORMAT STRING PARSER
#
#------------------------------------------------------------=

class FormatStringParser():
    """

    """

#   INIT
#
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


#   PARSE
#


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


#   COLLECT / SUPPRESS
#

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


#   MISC
#

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
