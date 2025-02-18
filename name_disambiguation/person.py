"""
The Person class represents a person's name and related information.
Can parse raw name strings into Person objects
"""

import copy
import re
import unittest
from collections import Counter

from nameparser import HumanName
from nameparser.config import CONSTANTS
from name_disambiguation.clean_org_names import RAW_ORG_TO_CLEAN_ORG_DICT

CONSTANTS.titles.remove(*CONSTANTS.titles)


class Person:
    """A Person object represents information of a person (possibly parsed from raw strings,
    or merged from different strings)
    Attributes:
        last (str): official parsed last name
        first (str): official parsed first name
        middle (str): official parsed middle name
        most_likely_org (str): most likely organization of the person
        positions (Counter of str): counter of all parsed organizations/extra information (must
                                    be clean official org names; can be in lower case)
        aliases (Counter of str): counter of raw names that correspond to the person
        count (int): number of times the person appeared in the data
    """
    def __init__(self, name_raw=None, last='', first='',    # pylint: disable=R0912,R0913,W0212
                 middle='',
                 positions=None, aliases=None, count=1, docs_authored=None, docs_received=None):
        """
        Returns a person object
        :param name_raw: raw string for the name (str)
        :param last: official parsed last name (if known) (str)
        :param first: official parsed first name (if known) (str)
        :param middle: official parsed middle name (if known) (str)
        :param positions: compilation of organizations/other information (if known) (Counter of str)
        :param aliases: Counter of raw strings that correspond to this person object (if known) (
        list of str)
        :param count: number of times the alias appeared in the data (int)
        """

        # initialize positions as an empty Counter if it is not given
        if positions is None:
            positions = Counter()

        if isinstance(positions, Counter):
            self.positions = positions
        else:
            # initialize positions as a Counter
            self.positions = Counter()
            for i in positions:
                cleaned = re.sub(r'\.', '', i)
                self.positions[cleaned.upper()] += count

        # if raw name is given, parse it using parse_raw_name() to get first, middle, last,
        # and positions
        if name_raw:
            first, middle, last, pos_raw = self.parse_raw_name(name_raw, count)
            if pos_raw:
                self.positions += pos_raw

        # by default, the raw name is an alias of the person
        # (we're changing the first/middle names based on new information, so keeping the original
        # name as an alias is important)
        if aliases is None:
            if name_raw is None:
                aliases = Counter()
            else:
                aliases = Counter({name_raw.upper(): count})

        # TODO: SR: do we really want all the first/last/middle names to be ALL CAPS?
        # set last, first, middle, position, positions: all converted to upper case
        # set aliases and count
        self.last = last.upper()
        self.first = first.upper()
        self.middle = middle.upper()
        #self.most_likely_org = most_likely_org
        # remove periods and convert to upper case
        if isinstance(positions, Counter):
            self.positions = positions
        else:
            # initialize positions as a Counter
            self.positions = Counter()
            for i in positions:
                cleaned = re.sub(r'\.', '', i)
                self.positions[cleaned.upper()] += count

        # if aliases passed in is a Counter, directly use it
        if isinstance(aliases, Counter):
            self.aliases = aliases
        # else, loop through aliases to set up the Counter
        else:
            self.aliases = Counter()
            for i in aliases:
                self.aliases[i.upper()] += count

        if docs_authored:
            if isinstance(docs_authored, set):
                self.docs_authored = docs_authored
            else:
                raise ValueError("docs_authored for Person object has to be a set.")

        if docs_received:
            if isinstance(docs_received, set):
                self.docs_received = docs_received
            else:
                raise ValueError("docs_received for Person object has to be a set.")

        self.count = count

    def __repr__(self):
        """
        Returns string representation of first, middle, last name, positions,
        and all aliases
        :return: str of first, middle, last, positions, aliases
        """
        str_name = self.full_name + f'   F:{self.first} M:{self.middle} L:{self.last}'
        str_name = str_name + ", Position: " + str(self.positions) + ", Aliases: " + \
            str(self.aliases.most_common()) + ", count: " + str(self.count)
        return str_name

    def __eq__(self, other):
        """
        Compares two person object using hash (which hashes the string of last, first, middle,
        position, positions, aliases, and count)
        :param other: another person object
        :return: bool (if two person objects are the same)
        """
        return hash(self) == hash(other)

    def __lt__(self, other):

        return self.stemmed() < other.stemmed()

    def copy(self):
        """
        Copies a person object
        :return: a copied person object
        """
        return Person(last=self.last, first=self.first, middle=self.middle,
                      positions=copy.deepcopy(self.positions),
                      aliases=copy.deepcopy(self.aliases), count=self.count)

    def __hash__(self):
        """
        Hashes the person
        :return: hash (int)
        """
        return hash(f'{self.last} {self.first} {self.middle} {self.positions} {self.aliases}')

    def stemmed(self):
        """
        Returns only the official name ("LAST FIRST MIDDLE") of the person
        :return: str of official name
        """
        return f'{self.last} {self.first} {self.middle}'

    @property
    def full_name(self):
        """
        >>> from person import Person
        >>> Person(name_raw='DUNN,WL').full_name
        'W. L. Dunn'

        >>> Person(name_raw='Dunn, William Lee').full_name
        'William Lee Dunn'

        :return:
        """
        components = []
        if self.first:
            if len(self.first) == 1:
                components.append(self.first + '.')
            else:
                components.append(self.first.capitalize())

        if self.middle:
            if len(self.middle) == 1:
                components.append(self.middle + '.')
            else:
                components.append(self.middle.capitalize())

        if self.last:
            components.append(self.last.capitalize())

        return " ".join(components)

    @property
    def most_likely_position(self, official_org=True):      # pylint: disable=R0206
        """
        Calculates and sets most_likely_org as the organization with the highest number of count
        If official_org=True, returns official name of most common organization that is in
        RAW_ORG_TO_CLEAN_ORG_DICT (if none of the raw orgs are in the dict, return the most common)


        :param official_org: if consider only orgs in RAW_ORG_TO_CLEAN_ORG_DICT
        :return: None
        """

        if not official_org:
            print("WARNING! most_likely_position should always be run with official_org=True, even"
                  "just to correct spelling mistakes. Keeping around for compatibility and "
                  "possibly to see what organizations our offical list misses.")

        for position, position_count in self.positions.most_common():
            # a single mention of an affiliation is not enough to count. need at least 2
            if position_count == 1:
                return 'no positions available'

            # if we use the official orgs only and the position is in the official dict, then
            # we update the position to the corrected version.
            # otherwise, skip this position. w/o official position, just use the raw position.
            if official_org:
                if (position in RAW_ORG_TO_CLEAN_ORG_DICT and
                        RAW_ORG_TO_CLEAN_ORG_DICT[position] != "@skip@"):
                    return RAW_ORG_TO_CLEAN_ORG_DICT[position]
                else:
                    continue
            else:
                return position

        # if nothing found, return nothing found
        if len(self.positions) > 0:
            for position, _ in self.positions.most_common():
                if (
                        position in RAW_ORG_TO_CLEAN_ORG_DICT and
                        RAW_ORG_TO_CLEAN_ORG_DICT[position] == '@skip@'
                ):
                    continue
                if len(position) < 5:
                    continue

                return f'                                            {position.upper()}'


        return 'no positions available'



            # likely_position = self.positions.most_common(1)[0][0]
            # if official_org:
            #     for name in self.positions.most_common():
            #         if name[0] in RAW_ORG_TO_CLEAN_ORG_DICT and name[0] != '@skip@':
            #             likely_position = RAW_ORG_TO_CLEAN_ORG_DICT[name[0]]
            #             break
            # if likely_position == "@skip@":
            #     likely_position = 'no positions available'
            #     if len(self.positions) > 1:
            #         print(self.positions)
            #
            # return likely_position

    @staticmethod
    def remove_privlog_info(name_raw):
        """
        Remove privlog tag and info from raw name (e.g. 'Temko, Stanley L [Privlog:] TEMKO,SL')
        :param name_raw: the raw name alias
        :return: name_raw with privlog info tag removed
        """
        privlog_id = name_raw.find('[Privlog:]')
        if privlog_id == 0:
            return name_raw[privlog_id:]
        elif privlog_id > 0:
            return name_raw[:name_raw.find('[Privlog:]')]
        else:
            return name_raw

    @staticmethod
    def remove_jr_sr_iii(name_raw):
        """
        Remove Jr, Sr, and III from names if they follow the pattern Chumney-RD-Jr or
        Chumney-R-III

        >>> Person.remove_jr_sr_iii('Chumney-RD-Jr, oeuo')
        'Chumney-RD, oeuo'

        >>> Person.remove_jr_sr_iii('Chumney-R-III, oeuo')
        'Chumney-R, oeuo'

        >>> Person.remove_jr_sr_iii('Chumney-r-III, oeuo')
        'Chumney-r-III, oeuo'

        :param name_raw:
        :return:
        """

        # I don't know why it matches the whole group instead of just -Jr or -Sr
        match = re.search(r'^[A-Z][a-z]+-[A-Z]{1,2}(-Jr|-Sr|-III)', name_raw)
        if match:
            name_raw = name_raw.replace(match.group(1), '')
        return name_raw


    @staticmethod
    def parse_raw_name(name_raw: str, count: int, extract_orgs=True) -> (str, str, str, Counter):
        """
        Parses a (usually messy) raw name and returns
        first, middle, last names and a Counter of extracted positions

        extract_orgs tries to extract organizations from name. defaults to True. only set to False
        to be able to check if a name is valid (it prevents an infinite loop because by default,
        extracting organizations is part of the initialization of a person

        :param name_raw: str
        :param count: int
        :param extract_orgs: bool
        :return: str, str, str, Counter (first name, middle name, last name, positions Counter)
        """
        name_raw = Person.remove_privlog_info(name_raw)
        # remove JR, SR, or III if it follows this pattern: 'Chumney-RD-Jr'
        name_raw = Person.remove_jr_sr_iii(name_raw)

        # position is often attached with a dash,
        # e.g. 'BAKER, T E - NATIONAL ASSOCIATION OF ATTORNEYS'
        if name_raw.find(" - ") > -1 and len(name_raw.split(' - ')) == 2:
            name_raw, extracted_position = name_raw.split(" - ")
            extracted_positions = [extracted_position.strip()]
        else:
            extracted_positions = []

        # extract positions in parens e.g. Henson, A (Chadbourne & Park)
        paren_positions = re.findall(r'\([^(]+\)', name_raw)
        for position in paren_positions:
            extracted_positions.append(position.strip(',#() '))
            name_raw = name_raw.replace(position, '')

        # Search for known raw_org strings in name_raw, extract them as positions if necessary
        if extract_orgs:
            name_raw, new_positions = Person.extract_raw_org_names_from_name(name_raw)
            extracted_positions += new_positions

        # delete any leftover hashtags
        name_raw = name_raw.strip(' #')

        # Delete dashes between last name and initials
        # DUNN-W -> Dunn W
        if name_raw[-2] == '-':
            name_raw = name_raw[:-2] + " " + name_raw[-1:]
        # DUNN-WL -> DUNN WL
        if len(name_raw) > 2 and name_raw[-3] == '-':
            name_raw = name_raw[:-3] + " " + name_raw[-2:]

        # Parse current string using HumanName
        name = HumanName(name_raw)

        # e.g. Dunn W -> parsed as last name W. -> switch first/last
        if len(name.last) <= 2 < len(name.first):
            name.first, name.last = name.last, name.first

        # remove periods from initials
        if len(name.first) == 2 and name.first[1] == '.':
            name.first = name.first[0]
        if len(name.middle) == 2 and name.middle[1] == '.':
            name.middle = name.middle[0]

        # If first name is length 2 (Teague, CE), the two letters are most likely initials.
        if len(name.middle) == 0 and len(name.first) == 2:
            name.middle = name.first[1].upper()
            name.first = name.first[0].upper()

        # If first and middle initials have periods but not spaces -> separate, e.g. "R.K. Teague"
        if re.match(r'[a-zA-Z]\.[a-zA-Z]\.', name.first):
            name.middle = name.first[2]
            name.first = name.first[0]

        name.last = name.last.capitalize()
        name.first = name.first.capitalize()
        name.middle = name.middle.capitalize()

        # if multiple names are passed, they often end up in the middle name
        # e.g. 'Holtzman, A.,  Murray, J. ,  Henson, A.  -> only allow one comma or set to empty
        if name.middle.count(',') > 1:
            name.middle = ''

        if len(name.suffix) > 20 and name.suffix.count('.') > 2:
            name.suffix = ''

        if name.suffix:
            extracted_positions.append(name.suffix)

        # map organization names to clean official names (if they are in the dict) using
        # RAW_ORG_TO_CLEAN_ORG_DICT
        clean_orgs = []
        for raw_org in extracted_positions:
            if raw_org in RAW_ORG_TO_CLEAN_ORG_DICT:
                clean_org = RAW_ORG_TO_CLEAN_ORG_DICT[raw_org]
                if clean_org != '@skip@':
                    clean_orgs.append(clean_org)
            else:
                clean_orgs.append(raw_org)
        extracted_positions = clean_orgs

        # convert mapped positions into a counter
        result_positions = Counter()
        for position in extracted_positions:
            cleaned = re.sub(r'\.', '', position)
            result_positions[cleaned.upper()] += count

        # print(name.first, name.middle, name.last, result_positions)
        return name.first, name.middle, name.last, result_positions

    @staticmethod
    def extract_raw_org_names_from_name(name_raw):
        """
        Finds raw org names like "B&W" in a name string, standarizes them (e.g. to
        "Brown & Williamson," and returns the name without that raw org name + extracted positions


        :param name_raw: str
        :param extract_orgs: bool
        :return: str (name_raw without the raw org name), list of str (extracted clean
        organization names)
        """
        extracted_positions = []

        for raw_org, clean_org in RAW_ORG_TO_CLEAN_ORG_DICT.items():

            while True:
                search_hit = None
                # this is a bit of an ugly hack to get the last (rather than the first) search hit
                # for a string: we iterate over all matches and the last one gets stored in
                # search_hit

                for search_hit in re.finditer(r'\b' + raw_org + r'\b', name_raw):
                    pass

                if not search_hit:
                    break

                if len(raw_org) >= 3:
                    name_raw = name_raw[0:search_hit.start()] + name_raw[search_hit.end():]
                    if not clean_org == "@skip@":
                        extracted_positions.append(clean_org)

                elif len(raw_org) == 2:
                    name_raw_test = name_raw[0:search_hit.start()] + name_raw[search_hit.end():]

                    # test if deleted, there exists first & middle name
                    name = HumanName(name_raw_test)
                    # if first & middle name do not exist after deletion, the deleted org might
                    # actually be initials, so ignore the match
                    if not name.first and not name.middle:
                        break

                    # last names without middle names ("TEMKO") get interpreted as first names
                    # without last names. Skip those cases
                    if not name.last:
                        break

                    # if not, do extract raw_org
                    extracted_positions.append(clean_org)
                    name_raw = name_raw_test

        name_raw = name_raw.strip(', ')

        # more adventurous: try to extract organizations we don't have in the dictionary
        # do this only if a) the name is currently not valid (i.e. it has strange characters like
        # commas in the last name) and b) extracting an org makes it valid,
        # e.g. 'HOLMAN RT, DEUEL CONFERENCE ON LIPIDS'


        if len(name_raw) > 0:
            first, middle, last, _ = Person.parse_raw_name(name_raw, 0, extract_orgs=False)

            if not Person(last=last, middle=middle, first=first).check_if_this_person_looks_valid():
                search_hit = re.search(',.+$', name_raw)
                if search_hit:
                    extracted_position = name_raw[search_hit.start():].strip(', ')
                    name_raw_without_org = name_raw[0:search_hit.start()] + name_raw[
                        search_hit.end():]

                    # if raw name becomes valid after extracting the org, then we add it to the orgs
                    # otherwise, we skip it
                    first, middle, last, _ = Person.parse_raw_name(name_raw_without_org,
                                                                   0, extract_orgs=False)
                    if Person(last=last, middle=middle,
                              first=first).check_if_this_person_looks_valid():
                        extracted_positions.append(extracted_position)
                        name_raw = name_raw_without_org




        name_raw = name_raw.strip(', ')
        return name_raw, extracted_positions

    def check_if_this_person_looks_valid(self):         # pylint: disable=C0103
        """
        Checks if the initialized person looks valid, i.e. it has a first name or first initial,
        the last name doesn't have strange
        """

        status = True

        if (
                not re.match('^[a-zA-Z]+$', self.last) or
                not re.match('^[a-zA-Z]+$', self.first) or
                (len(self.middle) > 0 and not re.match('^[a-zA-Z]+$', self.middle))
        ):
            status = False

        return status



class TestNameChecker(unittest.TestCase):
    """
    Tests the check_if_this_person_looks_valid test
    """
    def test_check_if_this_person_looks_valid(self):        # pylint: disable=C0103
        """
        ibid.

        :return:
        """
        outcomes_and_names = [
            (True, Person(last='PEPPLES', first='E')),

            # no special characters in last or first name
            (False, Person(last='PEPPLES', first='Erest, B&W')),
            (False, Person(last='PEPPLES B&W', first='E')),

            # has to have a first name
            (False, Person(last='PEPPLES', first='')),

            # organizations should return False
            (False, Person(name_raw='US HOUSE COMM ON INTERSTATE AND FOREIGN COMMERCE'))
        ]

        for outcome, person in outcomes_and_names:
            print(person.check_if_this_person_looks_valid(), outcome, person)
            self.assertEqual(outcome, person.check_if_this_person_looks_valid())


class TestNameParser(unittest.TestCase):
    """Tests name parsing (parse_raw_name) of the Person class
    Attributes:
        test_raw_names: dict that corresponds raw names (str) to the expected Person object
    """
    def setUp(self):
        self.test_raw_names = {
        }

    # Not sure what the correct parsing is!
    # This one breaks. But I don't think it can be avoided.
    # >> > n = Person('Holtz, Jacob Alexander, Jacob & Medinger')
    # >> > n.last, n.first, n.middle, " ".join(n.positions).upper()
    # ('Holtz', '', '', 'JACOB ALEXANDER, JACOB & MEDINGER')

    def test_parse_name_1(self):
        """
        checks to see that a raw name is parsed correctly
        """
        # Also test Person constructor: use list as positions
        self.assertEqual(Person(last="Teague", first="C", middle="E", positions=Counter({'JR': 1}),
                                aliases=Counter(["TEAGUE CE JR"])),
                         Person(name_raw="TEAGUE CE JR"))

    def test_parse_name_2(self):
        """
        checks to see that a raw name is parsed correctly
        """
        # Also test Person constructor: use Counter as positions
        self.assertEqual(Person(last="Teague", first="C", middle="E", positions=Counter(["JR"]),
                                aliases=Counter(["TEAGUE CE JR"])),
                         Person(name_raw="teague ce jr"))

    # TODO parse JR & PHD in positions into two separate strings
    # def test_parse_name_3(self):
    #     """
    #     checks to see that a raw name is parsed correctly
    #     """
    #     # (currently parse them together, which is suboptimal but acceptable)
    #     self.assertEqual(Person(last="Teague", first="Claude", middle="Edward",
    #                             positions={"JR", "PHD"},
    #                             aliases=["Teague, Claude Edward, Jr., Ph.D."]),
    #                      Person(name_raw="Teague, Claude Edward, Jr., Ph.D."))

    def test_parse_name_4(self):
        """
        checks to see that a raw name is parsed correctly: test parsing of dashes
        """
        self.assertEqual(Person(last="Baker", first="T", middle="E",
                                positions={"NATIONAL ASSOCIATION OF ATTORNEYS GENERAL"},
                                aliases=Counter(["BAKER, T E - NATIONAL ASSOCIATION OF ATTORNEYS "
                                                 "GENERAL"])
                               ),
                         Person(name_raw="BAKER, T E - NATIONAL ASSOCIATION OF ATTORNEYS GENERAL"))

    def test_parse_name_5(self):
        """
        checks to see that a raw name is parsed correctly: test parsing of dashes
        """
        self.assertEqual(Person(last="Baker", first="C", middle="J", positions={},
                                aliases=Counter(["BAKER-CJ"])),
                         Person(name_raw="BAKER-cj"))

    def test_parse_name_6(self):
        """
        checks to see that a raw name is parsed correctly
        """
        # Not specify positions: test to make sure Person constructor can handle no data
        # Here we assume for "Baker, JR", it is more likely that JR are initials and not junior
        self.assertEqual(Person(last="Baker", first="J", middle="R",
                                aliases=Counter(["BAKER, JR"])),
                         Person(name_raw="Baker, JR"))

    def test_parse_name_7(self):
        """
        checks to see that a raw name is parsed correctly: test if parser ignores "#"
        """
        self.assertEqual(Person(last="Dunn", first="W", middle="L",
                                aliases=Counter(["DUNN WL #"])),
                         Person(name_raw="DUNN WL #"))

    def test_parse_name_8(self):
        """
        checks to see that a raw name is parsed correctly
        """
        self.assertEqual(Person(last="Dunn", first="W", middle="L",
                                aliases=Counter(["DUNN, W. L."])),
                         Person(name_raw="Dunn, W. L."))

    def test_parse_name_9(self):
        """
        checks to see that a raw name is parsed correctly
        """
        self.assertEqual(Person(last="Temko", first="S", middle="L",
                                positions=["COVINGTON & BURLING"],
                                aliases=Counter(["TEMKO SL, COVINGTON AND BURLING"])),
                         Person(name_raw="TEMKO SL, COVINGTON AND BURLING"))

    def test_parse_name_10(self):
        """
        checks to see that a raw name is parsed correctly: test if Privlog is handled correctly
        """
        self.assertEqual(Person(last="Temko", first="Stanley", middle="L",
                                aliases=Counter(["TEMKO, STANLEY L [PRIVLOG:] TEMKO,SL"])),
                         Person(name_raw="Temko, Stanley L [Privlog:] TEMKO,SL"))

    def test_parse_name_11(self):
        """
        checks to see that a raw name is parsed correctly
        """
        self.assertEqual(Person(last="Temko", first="S", middle="L",
                                positions=["Covington & Burling"],
                                aliases=Counter(["TEMKO-SL, COVINGTON & BURLING"])),
                         Person(name_raw="Temko-SL, Covington & Burling"))

    def test_parse_name_12(self):
        """
        checks to see that a raw name is parsed correctly:
        test if info inside parentheses is taken as positions
        """
        self.assertEqual(Person(last="Henson", first="A", middle="",
                                positions=["AMERICAN SENIOR VICE PRESIDENT AND GENERAL COUNSEL"],
                                aliases=Counter(["HENSON, A. (AMERICAN SENIOR VICE PRESIDENT AND "
                                                 "GENERAL COUNSEL)"])),
                         Person(name_raw="HENSON, A. (AMERICAN SENIOR VICE PRESIDENT AND GENERAL "
                                         "COUNSEL)"))

    def test_parse_name_13(self):
        """
        checks to see that a raw name is parsed correctly:
        test if only the first person's name is extracted if the raw string contain multiple people
        """
        self.assertEqual(Person(last="Henson", first="A", middle="",
                                positions=["CHADBOURNE, PARK, WHITESIDE & WOLFF"],
                                aliases=Counter(["HENSON, A. (CHADBOURNE, PARKE, WHITESIDE & "
                                                 "WOLFF, "
                                                 "AMERICAN OUTSIDE COUNSEL) (HANDWRITTEN NOTES)"])),
                         Person(name_raw="HENSON, A. (CHADBOURNE, PARKE, WHITESIDE & WOLFF, "
                                         "AMERICAN OUTSIDE COUNSEL) (HANDWRITTEN NOTES)"))

    # TODO fix when multiple names are in the same string, not parse remaining name as positions
    # def test_parse_name_14(self):
    #     """
    #     checks to see that a raw name is parsed correctly:
    #     test parsing of multiple people in raw string
    #     """
    #     # This one does not discard the rest of the names and instead stores in positions
    #     # (see test_parse_name_14b which correctly handles it when there are more names)
    #     print("positions: ", Person(name_raw="Holtzman, A.,  Murray, J. ,  Henson, A.").positions)
    #     self.assertEqual(Person(last="Holtzman", first="A", middle="", positions=[],
    #                             aliases=["Holtzman, A.,  Murray, J. ,  Henson, A."]),
    #                      Person(name_raw="Holtzman, A.,  Murray, J. ,  Henson, A."))

    def test_parse_name_14b(self):
        """
        checks to see that a raw name is parsed correctly: comparison to 14
        """
        self.assertEqual(Person(last="Holtzman", first="A", middle="", positions=[],
                                aliases=Counter(["HOLTZMAN, A.,  MURRAY, J. ,  HENSON, A. ,  "
                                                 "PEPPLES, E. ,  STEVENS, A. ,  WITT, S."])),
                         Person(name_raw="Holtzman, A.,  Murray, J. ,  Henson, A. ,  "
                                         "Pepples, E. ,  Stevens, A. ,  Witt, S."))

    def test_parse_name_15(self):
        """
        checks to see that a raw name is parsed correctly
        """
        self.assertEqual(Person(last="Holtz", first="Jacob", middle="",
                                positions=["Jacob & Medinger"],
                                aliases=Counter(["HOLTZ, JACOB, JACOB & MEDINGER"])),
                         Person(name_raw="Holtz, Jacob, Jacob & Medinger"))

    def test_parse_name_16(self):
        """
        checks to see that a raw name is parsed correctly
        """
        self.assertEqual(Person(last="Proctor", first="D", middle="F",
                                positions=["Johns Hopkins University"],
                                aliases=Counter(["PROCTOR DF, JOHNS HOPKINS SCHOOL OF HYGIENE"])),
                         Person(name_raw="PROCTOR DF, JOHNS HOPKINS SCHOOL OF HYGIENE"))

    def test_parse_name_17(self):
        """
        checks to see that a raw name is parsed correctly
        """
        self.assertEqual(Person(last="Smith", first="Andy", middle="B", positions=["JR"],
                                aliases=["SMITH, ANDY B, J.R."]),
                         Person(name_raw="Smith, Andy B, J.R."))

    def test_parse_name_18(self):
        """
        checks to see that a raw name is parsed correctly
        """
        self.assertEqual(Person(last="Cantrell", first="D", middle="",
                                positions=["BROWN & WILLIAMSON"], aliases=["D CANTRELL, B&W"]),
                         Person(name_raw="D Cantrell, B&W"))

    def test_parse_name_19(self):
        """
        checks to see that a raw name is parsed correctly
        """
        self.assertEqual(Person(last="Cantrell", first="A", middle="B",
                                positions=["BROWN & WILLIAMSON"], aliases=["A B CANTRELL, BW"]),
                         Person(name_raw="A B Cantrell, BW"))


class TestOrgParser(unittest.TestCase):
    """
    Tests organization parser and extracter in extract_raw_org_names_from_name
    """

    def test_parse_org_1(self):
        self.assertEqual(
            Person.extract_raw_org_names_from_name('TEMKO SL, COVINGTON AND BURLING'),
            ('TEMKO SL', ['Covington & Burling'])
        )

    def test_parse_org_2(self):
        # if an organization could also be name initials, keep the initials
        self.assertEqual(
            Person.extract_raw_org_names_from_name('TEMKO PM'),
            ('TEMKO PM', [])
        )

    def test_parse_org_3(self):
        self.assertEqual(
            Person.extract_raw_org_names_from_name('TEMKO PM, PM'),
            ('TEMKO PM', ['Philip Morris'])
        )

    def test_parse_org_4(self):
        # organizations in @skip@ like UNK (unknown) should be deleted
        self.assertEqual(
            Person.extract_raw_org_names_from_name('TEMKO PM, UNK'),
            ('TEMKO PM', [])
        )


if __name__ == '__main__':
    unittest.main()
