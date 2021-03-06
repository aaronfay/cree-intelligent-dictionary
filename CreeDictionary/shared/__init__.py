"""
shared (expensive) instances
"""

from typing import Dict, Iterable, Set, Tuple

from hfstol import HFSTOL
from utils import paradigm_filler as pf
from utils import shared_res_dir


class FilteredHFSTOL:
    """
    Acts like HFSTOL but removes analyses with +Err/Frag.
    """

    def __init__(self, transducer: HFSTOL):
        self._hfstol = transducer

    @staticmethod
    def _is_good_analysis(analysis: str) -> bool:
        return "+Err/Frag" not in analysis

    def feed_in_bulk_fast(
        self, surface_forms: Iterable[str], multi_process: int = 1
    ) -> Dict[str, Set[str]]:
        original = self._hfstol.feed_in_bulk_fast(
            surface_forms, multi_process=multi_process
        )
        return {
            wordform: {a for a in analyses if self._is_good_analysis(a)}
            for wordform, analyses in original.items()
        }


paradigm_filler = pf.ParadigmFiller.default_filler()

descriptive_analyzer = FilteredHFSTOL(
    HFSTOL.from_file(shared_res_dir / "fst" / "crk-descriptive-analyzer.hfstol")
)

strict_analyzer = FilteredHFSTOL(
    HFSTOL.from_file(shared_res_dir / "fst" / "crk-strict-analyzer.hfstol")
)

normative_generator = HFSTOL.from_file(
    shared_res_dir / "fst" / "crk-normative-generator.hfstol"
)
