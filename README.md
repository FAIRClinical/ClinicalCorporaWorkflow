# ClinicalCorporaWorkflow
This Python workflow is created for the gathering and standardisation of clinical case reports, producing BioC compliant articles including supplementary materials.

## Usage
It is advisable to execute this workflow with administrator privileges, with the following options:

Standard workflow execution:
```
python -m FAIRClinicalWorkflow -u "path_to_my_unrar_executable"
```

Process a specific PMC archive set number (e.g. set 030):
```
python -m FAIRClinicalWorkflow -u "path_to_my_unrar_executable" -s "030"
```


## Requirements
Developed and tested using Python version 3.10. All dependencies are listed in the pyproject.toml file provided, which was generated using the uv package manager. 

To attempt an older .doc file conversion to .docx format, additional requirements should be installed depending on the operating system:

**Windows**: Pywin32 python module AND a working installation of Microsoft Office.

**Linux**: A working installation of Libre Office.

**MAC**: A working installation of Microsoft Office.

Python dependencies can be installed from the pyproject.toml file using the following command:
```
uv pip install
```

### UnRaR
To ensure the best extraction of .rar archive types, please ensure you have the UnRaR executable available on your machine. The appropriate version for your operating system can be found here: https://www.rarlab.com/rar_add.htm 