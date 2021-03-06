import pytest
from API.models import Wordform
from DatabaseManager.__main__ import cmd_entry
from DatabaseManager.cree_inflection_generator import expand_inflections
from django.core.management import call_command


@pytest.mark.django_db
def test_import_nice_xml(shared_datadir):
    call_command("migrate", "API", "0001")
    cmd_entry([..., "import", str(shared_datadir / "crkeng-small-nice-0")])

    expanded = expand_inflections(
        ["yôwamêw+V+TA+Ind+3Sg+4Sg/PlO"], multi_processing=1, verbose=False
    )
    for analysis_and_inflections in expanded.values():
        for analysis, inflections in analysis_and_inflections:
            for inflection in inflections:
                assert len(Wordform.objects.filter(text=inflection)) >= 1
