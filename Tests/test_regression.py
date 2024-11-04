from pathlib import Path

import bioc

# Supplementary Unprocessed Tests

class TestUnprocessedLog:
    def __init__(self, set_name):
        self.pmc_set = set_name

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

TestUnprocessedLog("PMC000XXXXX").test_unprocessed_log()