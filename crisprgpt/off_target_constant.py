PROMPT_REQUEST_STEP1 = """🔍 To identify potential off-target sites for your genome editing guides, we recommend you using CRISPRitz (Cancellieri et al.,Bioinformatics,2020), a rapid, high-throughput and variant-aware in silico off-target site identification package.

👁 Please find the github page below:
https://github.com/pinellolab/CRISPRitz

📄 *Please cite the corresponding papers if you decide to use the tool.

❓ Are you hoping to perform (1). Mismatches-Only search or (2). Mismatches + Bulges search?"""

PROMPT_PROCESS_STEP1 = """
Please act as an expert in CRISPR technology. Given the user instruction and user input, think step by step and generate a choice for the user. Please format your response and make sure it is parsable by JSON.

User Instructions:

"Are you hoping to perform (1). Mismatches-Only search or (2). Mismatches + Bulges search?"

User Input:

"{user_message}"

Response format (JSON parsable):

{{
"Thoughts": "<thoughts>", ## think step-by-step and organize your thoughts here.
"Choice": "<choice>" ## choose between "1" and "2". 
}}"""

RESPONSE_MISMATCH_ONLY = """
🚀 To start with the package, please first install docker: https://docs.docker.com, then install the CRISPRitz through the docker.

📋 Next, you would need to prepare the following files:

- 📄 Your target genome directory: fasta format, needs to be separated into single chromosome files.
- 📋 Text file containing PAM info: including a number of Ns equal to the guide length and a space separated number indicating the length of the PAM sequence (e.g. Cas9 PAM is NNNNNNNNNNNNNNNNNNNNNGG 3)
- 📋 Text file containing one or more guides: including a number of Ns equal to the length of the PAM sequence (e.g. TCACCCAGGCTGGAATACAGNNN, the last 3 Ns represents the space occupied by the PAM in the real sequence)
- 📋 Text file (in .bed format): containing the genomic annotations.

➡️ Please run the code in the following sequence:

- 🔍 Search
```
docker run -v ${PWD}:/DATA -w /DATA -i pinellolab/crispritz crispritz.py search [your_ref_directory] [your_txt_pam_info] [your_txt_guides_info] [output_name] -mm [number of mismatches] -t -scores [your_ref_directory]
```

- 📌 Annotate
```
docker run -v ${PWD}:/DATA -w /DATA -i pinellolab/crispritz crispritz.py annotate-results [your targets file from 1] [your annotation file] [output_name]
```

- 📋 Generate report
```
docker run -v ${PWD}:/DATA -w /DATA -i pinellolab/crispritz crispritz.py generate-report [your sgRNA sequence] -mm [number of mismatch] -annotation [your annotation summary from 2] -extprofile [your extended profile file from 1] -gecko
```
"""

RESPONSE_MISMATCH_BULGES = """
🚀 To start with the package, please first install docker: https://docs.docker.com, then install the CRISPRitz through the docker.

📋 Next, you would need to prepare the following files:

- 📄 Your target genome directory: fasta format, needs to be separated into single chromosome files.
- 📋 Text file containing PAM info: including a number of Ns equal to the guide length and a space separated number indicating the length of the PAM sequence (e.g. Cas9 PAM is NNNNNNNNNNNNNNNNNNNNNGG 3)
- 📋 Text file containing one or more guides: including a number of Ns equal to the length of the PAM sequence (e.g. TCACCCAGGCTGGAATACAGNNN, the last 3 Ns represents the space occupied by the PAM in the real sequence)
- 📋 Text file (in .bed format): containing the genomic annotations.

➡️ Please run the code in the following sequence:

- ⏱️ Pre-index
```
docker run -v ${PWD}:/DATA -w /DATA -i pinellolab/crispritz crispritz.py index-genome [name of genome] [your_ref_directory] [your_txt_pam_info] -bMax [max number of bulges]
```

- 🔍 Search
```
docker run -v ${PWD}:/DATA -w /DATA -i pinellolab/crispritz crispritz.py search [your_pre-indexed_genome_directory] [your_txt_pam_info] [your_txt_guides_info] [output_name] -index -mm [number of mismatches] -bDNA [size of DNA bulge] -bRNA [size of RNA bulge] -t -scores [your_ref_directory]
```

- 📌 Annotate
```
docker run -v ${PWD}:/DATA -w /DATA -i pinellolab/crispritz crispritz.py annotate-results [your targets file from 1] [your annotation file] [output_name]
```

- 📋 Generate report
```
docker run -v ${PWD}:/DATA -w /DATA -i pinellolab/crispritz crispritz.py generate-report [your sgRNA sequence] -mm [number of mismatch] -annotation [your annotation summary from 2] -extprofile [your extended profile file from 1] -gecko
```
"""