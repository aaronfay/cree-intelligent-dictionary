import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import DefaultDict, Dict, List, NamedTuple, Set, Tuple

from django.conf import settings

from API.models import Definition, DictionarySource, EnglishKeyword, Wordform
from colorama import init
from DatabaseManager import xml_entry_lemma_finder
from DatabaseManager.cree_inflection_generator import expand_inflections
from DatabaseManager.log import DatabaseManagerLogger
from DatabaseManager.xml_consistency_checker import (
    does_inflectional_category_match_xml_entry,
)
from utils import PartOfSpeech, fst_analysis_parser
from utils.crkeng_xml_utils import (
    IndexedXML,
    convert_xml_inflectional_category_to_word_class,
)
from utils.data_classes import XMLEntry
from utils.profiling import timed

init()  # for windows compatibility

logger = DatabaseManagerLogger(__name__)

RECOGNIZABLE_POS: Set[str] = {p.value for p in PartOfSpeech}


def generate_as_is_analysis(xml_l: str, pos: str, ic: str) -> str:
    """
    generate analysis for xml entries whose lemmas cannot be determined.
    The philosophy is to match the appearance an fst analysis
    in the following examples, the xml_ls are not necessarily un-analyzable. They are just examples to show the
    behaviour of this function.

    >>> generate_as_is_analysis('ihtatwêwitam', 'V', 'VTI') # adopt more detailed ic if possible
    'ihtatwêwitam+V+TI'
    >>> generate_as_is_analysis('wayawîwin', 'N', 'NI-2') # adopt more detailed ic if possible, strip dash-x to simulate fst analysis
    'wayawîwin+N+I'
    >>> generate_as_is_analysis('wayawîwin', '', 'NI') # adopt more detailed ic if possible, strip dash-x to simulate fst analysis
    'wayawîwin+N+I'
    >>> generate_as_is_analysis('wayawîwin', 'N', 'IPP') # ignore inflectional category/word class outside utils.WordClass Enum
    'wayawîwin+N'
    >>> generate_as_is_analysis('wayawîwin', 'N', '') # use pos only as a fallback
    'wayawîwin+N'
    >>> generate_as_is_analysis('wayawîwin', '', '') # no analysis when there's no pos nor ic
    ''
    >>> generate_as_is_analysis('wayawîwin', '', 'IPP') # ignore inflectional category/word class outside utils.WordClass Enum
    ''
    """

    # possible parsed pos str
    # {'', 'IPV', 'Pron', 'N', 'Ipc', 'V', '-'}

    # possible parsed ic str
    # {'', 'NDA-1', 'NDI-?', 'NA-3', 'NA-4w', 'NDA-2', 'VTI-2', 'NDI-3', 'NDI-x', 'NDA-x',
    # 'IPJ  Exclamation', 'NI-5', 'NDA-4', 'VII-n', 'NDI-4', 'VTA-2', 'IPH', 'IPC ;; IPJ',
    # 'VAI-v', 'VTA-1', 'NI-3', 'VAI-n', 'NDA-4w', 'IPJ', 'PrI', 'NA-2', 'IPN', 'PR', 'IPV',
    # 'NA-?', 'NI-1', 'VTA-3', 'NI-?', 'VTA-4', 'VTI-3', 'NI-2', 'NA-4', 'NDI-1', 'NA-1', 'IPP',
    # 'NI-4w', 'INM', 'VTA-5', 'PrA', 'NDI-2', 'IPC', 'VTI-1', 'NI-4', 'NDA-3', 'VII-v', 'Interr'}

    ic = ic.split("-")[0]

    recognized_wc = convert_xml_inflectional_category_to_word_class(ic)

    if recognized_wc is None:
        if pos not in ("", "-"):
            return xml_l + "+" + pos
        else:
            return ""
    else:
        return xml_l + recognized_wc.to_fst_output_style()


def format_element_error(msg: str, element: ET.Element) -> str:
    """
    format a message about an element and prettified xml for the element

    e.g.

    missing <lc> element

    <e>
        <t>blah</t>
    </e>
    """
    return f"{msg} \n {ET.tostring(element, encoding='unicode')}"


class EngcrkCree(NamedTuple):
    """
    A cree word extracted from engcrk.xml.
    The corresponding wordform in the database is to be determined later
    """

    wordform: str
    pos: PartOfSpeech


def load_engcrk_xml(filename: Path) -> DefaultDict[EngcrkCree, List[str]]:
    """
    :return: Dict[EngcrkCree , [english1, english2, english3 ...]] pos is in uppercase
    """

    # The structure in engcrk.xml

    """
        <e>

            <lg xml:lang="eng">
                <l pos="N">August</l>
            </lg>

            <mg>
                <tg xml:lang="crk">
                    <trunc sources="MD">august. [The flying month].</trunc>
                    <t pos="N" rank="1.0">Ohpahow-pisim</t>
                </tg>
            </mg>

            <mg>
                <tg xml:lang="crk">
                    <trunc sources="CW">Flying-Up Moon; August</trunc>
                    <t pos="N" rank="1.0">ohpahowi-pîsim</t>
                </tg>
            </mg>
        </e>
    """

    filename = Path(filename)

    assert filename.exists(), "%s does not exist" % filename

    res: DefaultDict[EngcrkCree, List[str]] = defaultdict(list)

    root = ET.parse(str(filename)).getroot()
    elements = root.findall(".//e")

    for element in elements:
        l_element = element.find("lg/l")
        if l_element is None:
            logger.debug(
                format_element_error(f"<e> lacks an <l> in file {filename}", element)
            )
            continue

        if l_element.text is None:
            logger.debug(format_element_error("<l> does not have text", element))
            continue

        t_elements = element.findall("mg/tg/t")

        if not t_elements:
            logger.debug(
                format_element_error(f"<e> lacks <t> in file {filename}", element)
            )
            continue

        for t_element in t_elements:
            if t_element.text is None:
                logger.debug(
                    format_element_error(
                        f"<t> does not have text in file {filename}", element
                    )
                )
                continue
            cree_word = t_element.text
            pos_str = t_element.get("pos")
            assert pos_str is not None
            try:
                pos = PartOfSpeech(pos_str.upper())
            except ValueError:
                logger.debug(
                    format_element_error(
                        f"Cree word {cree_word} has a unrecognizable pos {pos_str}",
                        element,
                    )
                )
                continue

            res[EngcrkCree(cree_word, pos)].append(l_element.text)

    return res


def find_latest_xml_files(dir_name: Path) -> Tuple[Path, Path]:
    """
    Find the latest timestamped xml files, with un-timestamped files as a fallback if no timestamped file is found

    :raise FileNotFoundError: if either file can't be found
    """
    name_pattern = re.compile(
        r"^(?P<direction>(crkeng|engcrk)).*?(?P<timestamp>\d{6})?\.xml$"
    )

    crkeng_file_path_to_timestamp: Dict[Path, str] = {}
    engcrk_file_path_to_timestamp: Dict[Path, str] = {}

    for file in dir_name.glob("*.xml"):
        res = re.match(name_pattern, file.name)
        if res is not None:
            timestamp = "000000"
            if res.group("timestamp") is not None:
                timestamp = res.group("timestamp")
            if res.group("direction") == "crkeng":
                crkeng_file_path_to_timestamp[file] = timestamp
            else:  # engcrk
                engcrk_file_path_to_timestamp[file] = timestamp
    if len(crkeng_file_path_to_timestamp) == 0:
        raise FileNotFoundError(f"No legal xml files for crkeng found under {dir_name}")
    if len(engcrk_file_path_to_timestamp) == 0:
        raise FileNotFoundError(f"No legal xml files for engcrk found under {dir_name}")

    return (
        max(
            crkeng_file_path_to_timestamp, key=crkeng_file_path_to_timestamp.__getitem__
        ),
        max(
            engcrk_file_path_to_timestamp, key=engcrk_file_path_to_timestamp.__getitem__
        ),
    )


def import_sources():
    """
    Import dictionary sources to the dictionary.
    """

    for src in settings.MORPHODICT_SOURCES:
        DictionarySource(**src).save()


@timed()
def import_xmls(dir_name: Path, multi_processing: int = 1, verbose=True):
    """
    Import from crkeng and engcrk files, `dir_name` can host a series of xml files. The latest timestamped files will be
    used, with un-timestamped files as a fallback.

    :param multi_processing: Use multiple hfstol processes to speed up importing
    :param dir_name: the directory that has pattern (crkeng|engcrk).*?(?P<timestamp>\d{6})?\.xml
    (e.g. engcrk_cw_md_200319.xml or engcrk.xml) files, beware the timestamp has format yymmdd
    :param verbose: print to stdout or not
    """
    logger.set_print_info_on_console(verbose)

    crkeng_file_path, engcrk_file_path = find_latest_xml_files(dir_name)
    logger.info(f"using crkeng file: {crkeng_file_path}")
    logger.info(f"using engcrk file: {engcrk_file_path}")

    assert crkeng_file_path.exists() and engcrk_file_path.exists()

    with open(crkeng_file_path) as f:
        crkeng_xml = IndexedXML.from_xml_file(f)

    #     Note the source element from the XML file is not used:
    #
    #     <source id="CW">
    #         <title>Cree : Words / nehiyawewin : itwēwina</title>
    #     </source>
    #
    #     The sources specified in the settings are imported
    import_sources()

    source_abbreviations = crkeng_xml.source_abbreviations

    logger.info("Sources parsed: %r", source_abbreviations)
    for source_abbreviation in source_abbreviations:
        src = DictionarySource(abbrv=source_abbreviation)
        src.save()
        logger.info("Created source: %s", source_abbreviation)

    logger.info("Loading English keywords...")
    engcrk_cree_to_keywords = load_engcrk_xml(engcrk_file_path)
    logger.info("English keywords loaded")

    # these two will be imported to the database
    (
        identified_entry_to_analysis,
        as_is_entries,
    ) = xml_entry_lemma_finder.identify_entries(crkeng_xml, multi_processing)

    logger.info("Structuring wordforms, english keywords, and definition objects...")

    wordform_counter = 1
    definition_counter = 1
    keyword_counter = 1

    db_inflections: List[Wordform] = []
    db_definitions: List[Definition] = []
    db_keywords: List[EnglishKeyword] = []
    citations: Dict[int, Set[str]] = {}

    # now we import as is entries to the database, the entries that we fail to provide an lemma analysis.
    for entry in as_is_entries:
        upper_pos = entry.pos.upper()

        db_wordform = Wordform(
            id=wordform_counter,
            text=entry.l,
            analysis=generate_as_is_analysis(entry.l, entry.pos, entry.ic),
            pos=upper_pos if upper_pos in RECOGNIZABLE_POS else "",
            inflectional_category=entry.ic,
            is_lemma=True,  # is_lemma field should be true for as_is entries
            as_is=True,
        )

        if upper_pos in RECOGNIZABLE_POS:
            for english_keywords in engcrk_cree_to_keywords[
                EngcrkCree(entry.l, PartOfSpeech(upper_pos))
            ]:
                db_keywords.append(
                    EnglishKeyword(
                        id=keyword_counter, text=english_keywords, lemma=db_wordform
                    )
                )

                keyword_counter += 1

        db_wordform.lemma = db_wordform

        wordform_counter += 1
        db_inflections.append(db_wordform)

        for str_definition, source_strings in entry.translations:

            db_definition = Definition(
                id=definition_counter, text=str_definition, wordform=db_wordform
            )

            # Figure out what citations we should be making.
            assert definition_counter not in citations
            citations[definition_counter] = set(source_strings)

            definition_counter += 1
            db_definitions.append(db_definition)

    # generate ALL inflections within the paradigm tables from the lemma analysis
    expanded = expand_inflections(
        identified_entry_to_analysis.values(), multi_processing
    )

    # now we import identified entries to the database, the entries we successfully identify with their lemma analyses
    for (entry, lemma_analysis) in identified_entry_to_analysis.items():
        lemma_text_and_word_class = fst_analysis_parser.extract_lemma_text_and_word_class(
            lemma_analysis
        )
        assert lemma_text_and_word_class is not None

        fst_lemma_text, word_class = lemma_text_and_word_class
        generated_pos = word_class.pos

        db_wordforms_for_analysis = []
        db_lemma = None

        # build wordforms and definition in db
        for generated_analysis, generated_wordform_texts in expanded[lemma_analysis]:

            generated_lemma_text_and_ic = fst_analysis_parser.extract_lemma_text_and_word_class(
                generated_analysis
            )
            assert generated_lemma_text_and_ic is not None
            generated_lemma_text, generated_ic = generated_lemma_text_and_ic

            for generated_wordform_text in generated_wordform_texts:
                # generated_inflections contain different spellings of one fst analysis
                if (
                    generated_wordform_text == fst_lemma_text
                    and generated_analysis == lemma_analysis
                ):
                    is_lemma = True
                else:
                    is_lemma = False

                db_wordform = Wordform(
                    id=wordform_counter,
                    text=generated_wordform_text,
                    analysis=generated_analysis,
                    is_lemma=is_lemma,
                    pos=generated_pos.name,
                    inflectional_category=entry.ic,
                    as_is=False,
                )

                db_wordforms_for_analysis.append(db_wordform)
                wordform_counter += 1
                db_inflections.append(db_wordform)

                if is_lemma:
                    db_lemma = db_wordform
                    # as inflections sometimes bear definition with them
                    for english_keywords in engcrk_cree_to_keywords[
                        EngcrkCree(generated_wordform_text, generated_pos)
                    ]:
                        db_keywords.append(
                            EnglishKeyword(
                                id=keyword_counter,
                                text=english_keywords,
                                lemma=db_wordform,
                            )
                        )

                        keyword_counter += 1

                # now we create definition for all (possibly non-lemma) entries in the xml that are forms of this lemma.

                # try to match our generated wordform to entries in the xml file,
                # in order to get its translation from the entries
                entries_with_translations: List[XMLEntry] = []

                # first get homographic entries from the xml file
                homographic_entries = crkeng_xml.filter(l=generated_wordform_text)

                # The case when we do have homographic entries in xml,
                # Then we check whether these entries' pos and ic agrees with our generated wordform
                if len(homographic_entries) > 0:
                    for homographic_entry in homographic_entries:
                        if does_inflectional_category_match_xml_entry(
                            generated_ic, homographic_entry.pos, homographic_entry.ic
                        ):
                            entries_with_translations.append(homographic_entry)

                # The case when we don't have holographic entries in xml,
                # The generated inflection doesn't have a definition

                for entry_with_translation in entries_with_translations:

                    for (
                        str_definition,
                        source_strings,
                    ) in entry_with_translation.translations:
                        db_definition = Definition(
                            id=definition_counter,
                            text=str_definition,
                            wordform=db_wordform,
                        )
                        assert definition_counter not in citations
                        citations[definition_counter] = set(source_strings)

                        definition_counter += 1
                        db_definitions.append(db_definition)

        assert db_lemma is not None
        for wordform in db_wordforms_for_analysis:
            wordform.lemma = db_lemma

    logger.info("Inserting %d inflections to database..." % len(db_inflections))
    Wordform.objects.bulk_create(db_inflections)
    logger.info("Done inserting.")

    logger.info("Inserting definition to database...")
    Definition.objects.bulk_create(db_definitions)
    logger.info("Done inserting.")

    logger.info("Inserting citations [definition -> dictionary source] to database...")
    # ThroughModel is the "hidden" model that manages the Many-to-Many
    # relationship
    ThroughModel = Definition.citations.through

    def _generate_through_models():
        "Yields all associations between Definitions and DictionarySources"
        for dfn_id, src_ids in citations.items():
            for src_pk in src_ids:
                yield ThroughModel(definition_id=dfn_id, dictionarysource_id=src_pk)

    ThroughModel.objects.bulk_create(_generate_through_models())
    logger.info("Done inserting.")

    logger.info("Inserting English keywords to database...")
    EnglishKeyword.objects.bulk_create(db_keywords)
    logger.info("Done inserting.")

    # Convert the sources (stored as a string) to citations:
    for dfn in Definition.objects.all():
        source_ids = sorted(source.abbrv for source in dfn.citations.all())
        for source_id in source_ids:
            dfn.citations.add(source_id)
        dfn.save()
