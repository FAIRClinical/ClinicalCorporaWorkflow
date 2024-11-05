from pathlib import Path
from bioc import biocjson
# Supplementary Unprocessed Tests

class TestLogRecords:
    def __init__(self, set_name):
        self.pmc_set = set_name

    def test_title_log(self):
        # TODO: Solve the problem of tab characters being included legitimately in the article title/subtitle.
        log_path = Path(__file__).parent.joinpath("TestData") / F"{self.pmc_set}_json_ascii" / F"{self.pmc_set}_json_ascii_articles.tsv"
        assert log_path.exists()
        assert log_path.is_file()
        logged_articles = []
        with log_path.open() as f_in:
            for line in f_in:
                pmc_id, title = line.split("\t")
                title = title.rstrip("\n")
                article_path = log_path.parent / F"{pmc_id}.json"
                assert article_path.exists()
                assert article_path.is_file()
                with open(article_path, "r", encoding="utf-8") as article_f_in:
                    bioc_content = biocjson.load(article_f_in)
                file_title = bioc_content.documents[0].passages[0].text
                if "\t" in title:
                    file_subtitle = bioc_content.documents[0].passages[0].infons["subtitle"]
                    title, subtitle = title.split("\t")
                    assert title == file_title
                    assert subtitle == file_subtitle
                else:
                    assert title == file_title
                logged_articles.append(pmc_id)
        unlogged_articles = [x for x in log_path.parent.iterdir() if x.is_file() and x.endswith(".json")]
        assert not unlogged_articles


    def test_included_log(self):
        log_path = Path(__file__).parent.joinpath("TestData") / F"{self.pmc_set}_json_ascii_supplementary" / F"{self.pmc_set}_json_ascii_supplementary_included.tsv"
        assert log_path.exists()
        assert log_path.is_file()
        logged_included_files = []
        with log_path.open() as f_in:
            for line in f_in:
                pmc_dir, pmc_id, download_url = line.split("\t")
                assert "PMC" in pmc_id
                assert download_url.startswith("http")
                assert len(pmc_id) > 0
                assert len(download_url) > 0

                # Test whether the logged file name has been processed (it should not be)
                test_file_bioc = log_path.parent / pmc_dir / "Raw"
                file_name = download_url.split("/")[-1].rstrip("\n")
                test_file_bioc = test_file_bioc / file_name
                assert test_file_bioc.exists()
                assert test_file_bioc.is_file()
                logged_included_files.append((pmc_id, file_name))

    def test_excluded_log(self):
        log_path = Path(__file__).parent.joinpath("TestData") / F"{self.pmc_set}_json_ascii_supplementary" / F"{self.pmc_set}_json_ascii_supplementary_excluded.tsv"
        assert log_path.exists()
        assert log_path.is_file()
        logged_excluded_files = []
        with log_path.open() as f_in:
            for line in f_in:
                pmc_id, download_url = line.split("\t")
                assert "PMC" in pmc_id
                assert download_url.startswith("http")
                assert len(pmc_id) > 0
                assert len(download_url) > 0

                # Test whether the logged file name has been processed (it should not be)
                test_file_bioc = log_path.parent / F"{pmc_id}_supplementary" / "Raw"
                test_file_tables = log_path.parent / F"{pmc_id}_supplementary" / "Raw"
                file_name = download_url.split("/")[-1]
                test_file_bioc = test_file_bioc / F"{file_name}_bioc.json"
                test_file_tables = test_file_tables / F"{file_name}_tables.json"
                assert not test_file_bioc.exists()
                assert not test_file_tables.exists()
                logged_excluded_files.append((pmc_id, file_name))


    def test_unprocessed_log(self):
        log_path = Path(__file__).parent.joinpath("TestData") / F"{self.pmc_set}_json_ascii_supplementary" / F"{self.pmc_set}_json_ascii_supplementary_unprocessed.tsv"
        # Test if the log file is generated
        assert log_path.exists()
        assert log_path.is_file()
        logged_pmc_dirs = []
        with log_path.open() as f_in:
            for line in f_in:
                pmc_dir, pmc_id, file_name, optional_file, reason = line.split("\t")
                # Test whether the log values are present and correctly formatted
                assert "PMC" in pmc_dir
                assert "PMC" in pmc_id
                assert len(file_name) > 0
                assert len(reason) > 0
                # Test whether the logged file name has been processed (it should not be)
                test_file_bioc = log_path.parent / pmc_dir / "Processed" / F"{file_name}_bioc.json"
                test_file_tables = log_path.parent / pmc_dir / "Processed" / F"{file_name}_tables.json"
                assert not test_file_bioc.exists()
                assert not test_file_tables.exists()
                logged_pmc_dirs.append(pmc_dir)
        for pmc_dir in log_path.parent.iterdir():
            if pmc_dir.is_dir():
                processed_dir = log_path.parent / pmc_dir / "Processed"
                if processed_dir.exists():
                    assert pmc_dir not in logged_pmc_dirs
                else:
                    assert pmc_dir.name in logged_pmc_dirs

log_test = TestLogRecords("PMC000XXXXX")
log_test.test_unprocessed_log()
log_test.test_excluded_log()
log_test.test_included_log()
log_test.test_title_log()