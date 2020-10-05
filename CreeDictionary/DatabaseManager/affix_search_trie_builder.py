from utils.cree_lev_dist import remove_cree_diacritics
from API.models import AffixSearcher, Wordform
import logging


logger = logging.getLogger(__name__)


def initialize_affix_search():
    """
    build tries and attach to Wordform class to facilitate prefix/suffix search
    """
    logger.info("Building tries for affix search...")

    lowered_no_diacritics_text_with_id = [
        (remove_cree_diacritics(text.lower()), wf_id)
        for text, wf_id in Wordform.objects.filter(is_lemma=True).values_list(
            "text", "id"
        )
    ]

    Wordform.affix_searcher = AffixSearcher(lowered_no_diacritics_text_with_id)
    logger.info("Finished building tries")
