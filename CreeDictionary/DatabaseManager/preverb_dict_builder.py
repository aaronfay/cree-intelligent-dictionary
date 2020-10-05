from API.models import Wordform
from django.db.models import Q

from utils.cree_lev_dist import remove_cree_diacritics


def initialize_preverb_search():

    # Hashing to speed up exhaustive preverb matching
    # so that we won't need to search from the database every time the user searches for a preverb or when the user
    # query contains a preverb

    # todo: check if the below is still the case, It seems like preverbs without dashes have been removed
    #   from the source files
    # An all inclusive filtering mechanism is inflectional_category=IPV OR pos="IPV". Don't rely on a single one
    # due to the inconsistent labelling in the source crkeng.xml.
    # e.g. for preverb "pe", the source gives pos=Ipc ic=IPV.
    # For "sa", the source gives pos=IPV ic="" (unspecified)

    # after https://github.com/UAlbertaALTLab/cree-intelligent-dictionary/pull/262
    # many preverbs are normalized so that both inflectional_category and pos are set to IPV.
    for preverb_wordform in Wordform.objects.filter(
        Q(inflectional_category="IPV") | Q(pos="IPV")
    ):
        if not preverb_wordform.md_only:
            Wordform.PREVERB_ASCII_LOOKUP[
                remove_cree_diacritics(preverb_wordform.text.strip("-"))
            ].add(preverb_wordform)
