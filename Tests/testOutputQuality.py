from pathlib import Path

from FAIRClinicalWorkflow.AC.supplementary_processor import word_extensions, spreadsheet_extensions, image_extensions
from FAIRClinicalWorkflow.WorkflowStats import powerpoint_extensions

test_sets = [x for x in Path("TestData").iterdir() if x.is_dir()]

file_stats = {"missing_files": [], "old_count": 0, "new_count": 0, "files": []}
overall_stats = {"Spreadsheets": file_stats, "Words": file_stats,
                 "Presentations": file_stats,
                 "Images": file_stats, "PDFs": file_stats}


def count_processed_file_types(files, print_output=False):
    word_count = 0
    presentation_count = 0
    image_count = 0
    spreadsheet_count = 0
    pdf_count = 0

    for file in files:
        file_extension = "." + file.name.split(".")[-2].replace("_bioc", "")
        file_extension = file_extension.lower()
        if any(x for x in word_extensions if x in file_extension):
            word_count += 1
        elif any(x for x in powerpoint_extensions if x in file_extension):
            presentation_count += 1
        elif any(x for x in image_extensions if x in file_extension):
            image_count += 1
        elif any(x for x in spreadsheet_extensions if x in file_extension):
            spreadsheet_count += 1
        elif ".pdf" in file_extension:
            if "_tables" in file_extension:
                continue
            pdf_count += 1
        else:
            if print_output:
                print(F"{file.name} has no discernible type")
            else:
                continue

    if print_output:
        print(f"""
        File Types Processed
        --------------------
        Word files: {word_count}
        Presentation files: {presentation_count}
        Image files: {image_count}
        Spreadsheet files: {spreadsheet_count}
        PDF files: {pdf_count}
        --------------------
        """)

    return {"Spreadsheets": spreadsheet_count, "Words": word_count, "Presentations": presentation_count,
            "Images": image_count, "PDFs": pdf_count}


def test_output_quantity(test_supp_files, new_supp_files):
    original_file_counts = count_processed_file_types(test_supp_files)

    new_file_counts = count_processed_file_types(new_supp_files)

    for file_type in original_file_counts.keys():
        old_value = original_file_counts[file_type]
        new_value = new_file_counts[file_type]
        if old_value < new_value:
            print(F"{file_type} - {new_value - old_value} more output files")
        elif old_value > new_value:
            print(F"{file_type} - {old_value - new_value} less output files")
        else:
            print(F"{file_type} - same quantity")

        overall_stats[file_type]["new_count"] = new_value
        overall_stats[file_type]["old_count"] = old_value


def run_tests():
    for test_set in test_sets:
        test_supp_files = [x for x in test_set.rglob("*") if "Processed" in str(x.parent) and x.is_file()]

        new_set = test_set.absolute().parent.parent.parent / "FAIRClinicalWorkflow" / "Output" / test_set.name
        new_supp_files = [x for x in new_set.rglob("*") if "Processed" in str(x.parent) and x.is_file()]

        test_output_quantity(test_supp_files, new_supp_files)


run_tests()
