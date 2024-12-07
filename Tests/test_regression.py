from pathlib import Path
from bioc import biocjson
pmc_set = "PMC105XXXXX"

def test_title_log():
    log_path = Path(__file__).parent.joinpath("TestData") / F"{pmc_set}_json_ascii" / F"{pmc_set}_json_ascii_articles.tsv"
    assert log_path.exists(), "The full-text article log does not exist"
    assert log_path.is_file(), "The full-text article log is not a valid file"
    logged_articles = []
    with log_path.open() as f_in:
        for line in f_in:
            pmc_id, title = line.split("\t")
            title = title.rstrip("\n")
            article_path = log_path.parent / F"{pmc_id}.json"
            assert article_path.exists(), F"Article found within the full-text article log does not exist: {pmc_id}"
            assert article_path.is_file(), F"Article found within the full-text article log is invalid: {pmc_id}"
            with open(article_path, "r", encoding="utf-8") as article_f_in:
                bioc_content = biocjson.load(article_f_in)
            file_title = bioc_content.documents[0].passages[0].text.replace("\t", " ")
            if "subtitle" in bioc_content.documents[0].passages[0].infons:
                file_title = file_title + " " + bioc_content.documents[0].passages[0].infons["subtitle"]
            assert title == file_title or file_title.startswith(title), f"Article title does not match the title \
            logged within the full-text article log: {pmc_id}"
            logged_articles.append(pmc_id)
    unlogged_articles = [x.name for x in log_path.parent.iterdir() if x.is_file() and str(x).endswith(".json") \
                         and x.name.rstrip(".json") not in logged_articles]
    assert not unlogged_articles, F"Unlogged full-text articles have been found: {','.join(unlogged_articles)}"


def test_included_log():
    log_path = Path(__file__).parent.joinpath("TestData") / F"{pmc_set}_json_ascii_supplementary" / F"{pmc_set}_json_ascii_supplementary_included.tsv"
    assert log_path.exists(), F"The supplementary included log file does not exist"
    assert log_path.is_file(), F"The supplementary included log file is invalid"
    logged_included_files = []
    with log_path.open() as f_in:
        for line in f_in:
            pmc_dir, pmc_id, download_url = line.split("\t")
            assert "PMC" in pmc_id, F"Supplementary included log record does not contain a valid PMC ID format: {line}"
            assert download_url.startswith("http"), F"Supplementary included log record download url does not start with http: {line}"

            # Test whether the logged file name has been processed (it should not be)
            test_file_bioc = log_path.parent / pmc_dir / "Raw"
            file_name = download_url.split("/")[-1].rstrip("\n")
            test_file_bioc = test_file_bioc / file_name
            assert test_file_bioc.exists(), F"File recorded in the supplementary included log does not exist: {pmc_id}"
            assert test_file_bioc.is_file(), F"File recorded in the supplementary included log is not valid: {pmc_id}"
            logged_included_files.append((pmc_id, file_name))

def test_excluded_log():
    log_path = Path(__file__).parent.joinpath("TestData") / F"{pmc_set}_json_ascii_supplementary" / F"{pmc_set}_json_ascii_supplementary_excluded.tsv"
    assert log_path.exists()
    assert log_path.is_file()
    logged_excluded_files = []
    with log_path.open() as f_in:
        for line in f_in:
            pmc_id, download_url = line.split("\t", maxsplit=1)
            if "\t" in download_url:
                download_url, archived_file = download_url.split("\t")
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


def test_unprocessed_log():
    log_path = Path(__file__).parent.joinpath("TestData") / F"{pmc_set}_json_ascii_supplementary" / F"{pmc_set}_json_ascii_supplementary_unprocessed.tsv"
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
            logged_pmc_dirs.append((pmc_dir, file_name))
    for pmc_dir in log_path.parent.iterdir():
        if pmc_dir.is_dir():
            processed_dir = log_path.parent / pmc_dir / "Processed"
            if processed_dir.exists():
                for file in processed_dir.iterdir():
                    if file.is_file():
                        assert (pmc_dir, file) not in logged_pmc_dirs
            else:
                assert pmc_dir not in [x for (x, y) in logged_pmc_dirs]