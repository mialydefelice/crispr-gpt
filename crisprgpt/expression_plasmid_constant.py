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

PROMPT_PROCESS_CUSTOM_BACKBONE_EXPRESSION = """
You are an expert in plasmid and expression vector design.

Your task is to extract, validate, and (when necessary) infer plasmid backbone information from the user input below. 
You must return a SINGLE valid JSON object matching the schema exactly. 
Do not include any text outside the JSON object.

────────────────────────
INSTRUCTIONS
────────────────────────

1. Plasmid identification
- If a plasmid name is mentioned, normalize it to the closest known plasmid name.
- If not clear plasmid name is provided, try to determine a suitable plasmid based on details given in the user specifications, and put the suggestion in the filed BackboneName.
- If no suitable plasmid can be determined, leave "BackboneName" as an empty string.
- If an accession number is mentioned or can be confidently determined, include it.
  Otherwise set "BackboneAccession" = "".

2. Sequence handling
- If the user provides a DNA sequence (containing only A, T, G, C characters, case-insensitive):
  - Set "SequenceProvided" = true
  - Place the FULL sequence (uppercase, no spaces or line breaks) in "SequenceExtracted"
- If the user does NOT provide a sequence:
  - Set "SequenceProvided" = false
  - If a plasmid name or identifying details are provided, or a plasmid backbone is selected within the plasmid identification step, attempt to look up the plasmid sequence
    using reputable public sources (e.g., Addgene, Addgene Vector Database, Invitrogen, Promega, NCBI).
  - If a sequence is successfully found, place it in "SequenceExtracted".
  - If no sequence can be confidently obtained, leave "SequenceExtracted" as an empty string.
  - Do not make up a sequence. Do not modify any sequence you find. Strip any trailing whitespace.

3. URL handling
- If the user provides a URL, include it in "BackboneURL". Do not modify the URL.
- If no URL is provided but a plasmid name or accession is identified, attempt to find a reputable URL for that plasmid (e.g., Addgene, NCBI).
- If the URL does not contain an extractable sequence, leave "SequenceExtracted" empty.
- Do not halucinate URLs. If providing a URL is not possible, leave "BackboneURL" as an empty string.
- If providing a URL, ensure it is a valid link to a reputable source for plasmid information (e.g., Addgene, NCBI).

4. Feature inference
- If Promoter, SelectionMarker, or Origin are explicitly mentioned, extract them.
- If not mentioned, attempt to infer them from the identified plasmid when possible.
- If inference is not possible, leave the field as an empty string.

5. General descriptions
- If the user provides only a general description (e.g., desired expression system or features):
  - Suggest a reasonable plasmid backbone that matches most or all criteria.
  - Populate "Details" with a clear justification for why this plasmid was selected.

6. Status field
- Use "confirmed" only if the plasmid identity and/or sequence is confidently determined.
- Use "needs_clarification" if key information is missing or uncertain.

────────────────────────
USER INPUT
────────────────────────
{user_message}

────────────────────────
RESPONSE FORMAT (JSON ONLY)
────────────────────────
{{
  "BackboneName": "",
  "BackboneAccession": "",
  "SequenceProvided": false,
  "SequenceExtracted": "",
  "Details": "",
  "Status": "",
  "BackboneURL": "",
  "Promoter": "",
  "SelectionMarker": "",
  "Origin": ""
}}"""
