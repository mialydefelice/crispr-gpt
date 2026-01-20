PROMPT_REQUEST_AGENT1 = """
We can help you design your gene insert for expression plasmids.

Do you already have the exact DNA sequence for the gene you want to express? 

If YES: Please provide the sequence (in FASTA or raw format)
If NO: Please tell us the gene name or protein you want to express (e.g., "EGFP", "human TP53"), and we can look up and extract the sequence for you.
"""

PROMPT_PROCESS_AGENT1 = """Please act as an assistant to molecular biologists. Given the user input about gene insert design, determine whether they have the exact sequence or if we need to look it up. Please format your response as JSON.

Instruction:

If the user provides a DNA sequence (ATGC...) or mentions they have the exact sequence, respond that they have it.
If the user provides a gene name (e.g., EGFP, TP53), respond that we need to look it up.

User Input:

{user_message}

Response format (JSON):
{{
    "Has exact sequence": # yes or no
    "Target gene": # extracted gene name or identifier. If not available, output NA.
    "Sequence provided": # if user provided a sequence, summarize it (first 50 chars and length). Otherwise null.
    "Suggested variants": # if applicable, suggest variants. Otherwise empty list.
    "rationale": # explanation of your analysis.
}}"""

PROMPT_REQUEST_ENTRY_EXPRESSION = """Now, let's start designing your expression plasmid construct. We will guide you through a step by step process as listed below:
1. Selecting an expression plasmid backbone.
2. Designing the gene insert.
3. Selecting output format for your construct.
"""

PROMPT_STEP1_EXPRESSION = """
Step 1. Selecting an expression plasmid backbone

The plasmid backbone is the foundation of your expression construct. You can either:

A. Choose from our curated plasmid options:
   1. pcDNA3.1(+) - Industry-standard mammalian expression vector with CMV promoter
   2. pAG - Mammalian expression vector with SV40 promoter and selection options

B. Provide your own plasmid backbone:
   3. I have my own plasmid sequence or backbone
   4. I know the plasmid name and can provide details

Please select which option applies to you:
1. I want to use pcDNA3.1(+)
2. I want to use pAG
3. I have my own plasmid backbone
4. I know the plasmid name/details
"""

PROMPT_REQUEST_STEP1_INQUIRY_EXPRESSION = """
Which expression plasmid backbone would you like to use?
1. pcDNA3.1(+)
2. pAG
3. I have my own plasmid backbone
4. I know the plasmid name/details

Please select 1, 2, 3, or 4.
"""

PROMPT_PROCESS_STEP1_BACKBONE_INQUIRY_EXPRESSION = """Please act as an expert in plasmid design and mammalian cell expression systems. Given the instruction and user input, identify which plasmid backbone option the user selected.

Instruction:

The user is selecting from these options:
1. pcDNA3.1(+) - CMV promoter vector
2. pAG - SV40 promoter vector
3. User's own plasmid sequence/backbone
4. User's plasmid by name or reference

Determine which option they selected and extract relevant information.

User Input:

{user_message}

Please provide your response in JSON format:
{{
"Thoughts": "<thoughts>", # Analyze which option was selected
"BackboneName": "<option selected>", # The selected backbone (pcDNA3.1(+), pAG, custom, or by-name)
"CustomDetails": "<details if custom>", # If user provided custom backbone, include key details
"Status": "<confirmed or needs_details>"
}}"""


PROMPT_STEP1_BACKBONES_EXPRESSION = """
Step 1. Expression Plasmid Backbone Options

We offer two industry-standard plasmid backbones for expression, or you can provide your own:

BACKBONE A: pcDNA3.1(+)

This is an industry-standard mammalian expression vector widely used for transient and stable transfection.
- Promoter: CMV (adjustable for different expression levels: low, medium, high)
- Features: High copy number (pBR322 origin), Ampicillin selection marker, ~5.4 kb backbone
- Applications: Transient expression, stable cell lines, functional studies
- Reference: Invitrogen/Thermo Fisher

BACKBONE B: pAG

This is a mammalian expression vector with selection options.
- Promoter: SV40 (adjustable for different expression levels: low, medium, high)
- Features: pBR322 origin, Neomycin/Kanamycin selection marker, ~5.6 kb backbone
- Applications: Stable and transient expression, selection-based studies
- Reference: Addgene

OPTION C: Custom Backbone

If you have your own plasmid backbone:
- Provide the plasmid sequence (FASTA or GenBank format)
- Or provide the plasmid name and key features (promoter, selection marker, size, origin)

Please select which backbone you would like to use:
1. pcDNA3.1(+)
2. pAG
3. Custom - I have my own sequence
4. Custom - I know the plasmid name/details
"""

PROMPT_STEP2_EXPRESSION = """
Step 2. Designing the Gene Insert

Now that you have selected your expression plasmid backbone, the next step is to specify the gene you want to express.

You have three options for providing your gene insert:

Option A: Provide the exact DNA sequence
- Paste the coding sequence (CDS) in FASTA or GenBank format
- Include or exclude 5' UTR and 3' UTR as desired
- We will validate and prepare for cloning

Option B: Provide the gene name
- Specify the gene name (e.g., "EGFP", "TP53", "BRCA1")
- We will look up the sequence for you

Option C: Provide protein sequence
- Provide the amino acid sequence
- We will back-translate to DNA sequence

Please select which option applies to you and provide the corresponding information.
"""

PROMPT_REQUEST_STEP2_INQUIRY_EXPRESSION = """
How would you like to provide your gene insert?
1. I have the exact DNA sequence
2. I have the gene name (e.g., EGFP, TP53)
3. I have the protein amino acid sequence

Please select 1, 2, or 3 and provide the corresponding information.
"""

PROMPT_REQUEST_CUSTOM_BACKBONE_EXPRESSION = """
You indicated you want to use a custom plasmid backbone.

Please provide one of the following:

Option A: Plasmid Sequence
- Paste the complete plasmid sequence in FASTA or GenBank format
- Example: >plasmid_name or LOCUS plasmid_name...

Option B: Plasmid Details
- Plasmid name (e.g., "pEGFP-N1", "pUC19")
- Key features: promoter type, selection marker(s), origin of replication, approximate size
- Example: "My plasmid has CMV promoter, Ampicillin resistance, pBR322 origin, ~6 kb"

Please provide as much detail as possible.
"""

PROMPT_PROCESS_CUSTOM_BACKBONE_EXPRESSION = """Please act as an expert in plasmid design. Given the user input about a custom plasmid backbone, extract and validate the provided information. Format your response as JSON.

Instruction:

If the user provides a sequence (containing ATGC letters), extract key information and the sequence. Put the full sequence into the SequenceProvided field.
If the user provides plasmid details/name, organize the information provided, and use the information to look up the relevant plasmid and get the sequence. Most obvious places to look are at addgene.org, https://www.addgene.org/vector-database, invitrogen.com, promega.com and other similar sites. Save this sequence within the SequenceExtracted field.
If the user provides a URL, go to the website and look for the plasmid sequence and details there.

User Input:

{user_message}

Response format (JSON):
{{
"BackboneName": "<Look through the user provided text and extract a the plasmid name. Try to match and format to known plasmid names enter as 'tbd' if unknown>",
"BackboneAccession":"<Extract accession number if mentioned or if the backbone name is given, try to determine the accession number from known databases. If not available, enter 'NA'>",
"SequenceLength": "<length in bp if provided, or NA>",
"Promoter": "<promoter type if mentioned>",
"SelectionMarker": "<selection marker if mentioned>",
"Origin": "<origin of replication if mentioned>",
"SequenceProvided": "<yes or no>",
"SequenceExtracted": "<Full plasmid sequence if this was extracted for the user from an input name and details or if the User provided the plasmid sequence directly.>",
"Details": "<summary of provided information>",
"Status": "<confirmed or needs_clarification>"
}}"""
