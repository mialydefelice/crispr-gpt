PROMPT_REQUEST_AGENT1 = """
🧬 We can help you design your gene insert for expression plasmids.

❓ Do you already have the exact DNA sequence for the gene you want to express?

✅ If YES: Please provide the sequence (in FASTA or raw format)
🔍 If NO: Please tell us the gene name or protein you want to express (e.g., "human EGFP", "mouse TP53"), and we can look up and extract the sequence for you.
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
    "Target gene": # Look for a gene name within the provided sequence. If FASTA was provided the name will be after >. If not available, output NA.
    "Sequence provided": # if user provided a sequence, summarize it (first 50 chars and length). Otherwise null.
    "Suggested variants": # if applicable, suggest variants. Otherwise empty list.
    "rationale": # explanation of your analysis.
}}"""

PROMPT_PROCESS_AGENT2 = """Please act as an assistant to molecular biologists. Given the user input and available functions, think step by step to extract target information and help draft actions to search for gene sequences. Please format your response as JSON.

User Input:

{user_message}

Database columns:

Gene Symbol
Species
Sequence Type
Codon Optimization Status
Expression Level (predicted)
Codon Adaptation Index (CAI)
GC Content (%)
Secondary Structure Risk
Validation Status
Source Database

Available Functions:

1. subset_value: Subset the rows where the specified column matches the given value.
    Parameters:
    column_name: The name of the column to match.
    matching_value: a list of values to match in the specified column.

2. sort: Sort the DataFrame based on values in the specified column.
    Parameters:
    column_name: The name of the column to sort by.
    ascending: Whether to sort in ascending order (TRUE for ascending, FALSE for descending).

3. get: Get the top N rows of the DataFrame.
    Parameters:
    n (int): The number of top rows to return.

4. subset_between: Subset the rows where the specified column's values are between x and y (inclusive).
    Parameters:
    column_name: The name of the column to match.
    x (float): The lower bound value. Defaults to NA.
    y (float): The upper bound value. Defaults to NA.

Response format: 
{{
    "Thoughts": # Think step by step to solve the task.
    "Species": # Extract target species from user request. Select from human and mouse. Do not output anything else.
    "Actions": 
    [ 
        {{
            "action_index": <index>, # Action index that counts from 1
            "called_function": <function>, # Function to perform. Should select one from subset_value, sort, get, and subset_between.
            "column_name": <column>, # Specified column in the column list to perform action. Output NA if not applicable.
            "matching_value": <value>, # Matching values based on user input. Separate the values by comma. Output NA if not applicable.
            "ascending": <ascending>, # Whether to sort in ascending order based on user input. If it's true, output TRUE, else output FALSE. Output NA if not applicable.
            "n": <n>, # The number of top rows to return. Output a single number only. Default is 4. Output NA if not applicable.
            "x": <x>, # The lower bound value to return. Output a single number only. Default is NA. Output NA if not applicable.
            "y": <y> # The upper bound value to return. Output a single number only. Default is NA. Output NA if not applicable.
        }},
    ] ## A list of actions.
}}"""


PROMPT_REQUEST_PLASMID_BACKBONE_CHOICE = """
⚙️ Before we finalize your gene insert design, please confirm your choice of expression plasmid backbone.

Which plasmid backbone would you like to use?

1️⃣ I already selected a plasmid backbone and want to proceed with the gene insert design
2️⃣ I need to review or change my plasmid backbone selection
3️⃣ I want to view recommendations again
"""

PROMPT_PROCESS_PLASMID_BACKBONE_CHOICE = """Please act as an expert in plasmid design. Given the user instruction and user input, determine whether the user is ready to proceed with gene insert design. Please format your response as JSON.

User Instructions:

"Before we finalize your gene insert design, please confirm your choice of expression plasmid backbone."

User Input:

{user_message}

Response format:

{{
"Thoughts": "<thoughts>",
"Status": "<proceed_or_review>", # Select from PROCEED_WITH_INSERT_DESIGN or REVIEW_BACKBONE_SELECTION
"Backbone Confirmation": "<confirmed_or_needs_change>" # Indicate if backbone selection is confirmed
}}"""


RESPONSE_STEP_ERROR = """
⚠️ Sorry, we could not find an optimized sequence for your gene in our database.

While we can suggest some great resources and online tools to help you design and optimize your gene insert:

1️⃣ You could use pre-optimized genes from commercial vendors:
   (i) GenScript: https://www.genscript.com/codon-optimization.html
   (ii) Integrated DNA Technologies (IDT): https://www.idtdna.com/pages/products/custom-dna/gene-optimization
   (iii) Synthego: https://www.synthego.com/optimize-gene

2️⃣ You could use free online codon optimization tools:
   (i) Codon Adaptation Index Calculator: https://www.genscript.com/cai-codon-usage-analyzer.html
   (ii) OPTIMIZER: https://genomes.urmc.rochester.edu/
   (iii) JCat (Java Codon Adaptation Tool): https://www.genscript.com/jcat.html
   (iv) COOL (Codon Optimizer OnLine): http://www.coolguides.de/

3️⃣ You could use your preferred DNA synthesis vendor's design tools and optimization services.

4️⃣ You could provide us with the raw gene sequence and we can help guide optimization.

📄 *Please cite the corresponding papers if you use these tools or services.
"""

PROMPT_REQUEST_SEQUENCE_VALIDATION = """
✅ Great! We have your target gene. Here's a summary of your construct:

1️⃣ Target Gene: {gene_name}
2️⃣ Plasmid Backbone: {backbone_name}

❓ Would you like to proceed with this construct, or would you like to make any modifications?
"""

# To be added later
future_additions: """
3. Predicted Protein Expression Level: {predicted_expression_level}
4. Important Featuress to Check:
    - Start Codont (ATG) present: {start_codon_present}
    - Stop Codon present: {stop_codon_present}
    - GC Content (%): {gc_content}
"""

PROMPT_PROCESS_SEQUENCE_VALIDATION = """Please act as an expert in molecular cloning. Given the user instruction and input about construct validation, determine whether the user is satisfied with the design or wants modifications. Please format your response as JSON.

User Instructions:

"Before proceeding with cloning and expression, let's validate your final construct..."

User Input:

{user_message}

Response format:

{{
"Thoughts": "<thoughts>",
"Status": "<proceed_or_modify>", # Select from PROCEED_WITH_CLONING or REQUEST_MODIFICATIONS
"Modifications": "<list_of_requested_changes>", # If modifying, specify what changes are needed
"Confidence": "<high_or_moderate_or_low>" # User confidence in the design
}}"""


PROMPT_REQUEST_OUTPUT_FORMAT = """
🌟 Excellent! Your expression construct design is complete. We are ready to provide you with the final sequence for ordering.

In what format would you like to receive your plasmid sequence for ordering?

1️⃣ GenBank format (.gb) - Complete annotation with features and metadata
2️⃣ FASTA format (.fasta) - Sequence header and nucleotide sequence
3️⃣ Raw sequence string - Nucleotide sequence only

📄 Please select your preferred format (1, 2, or 3). You can use this sequence file to submit to your DNA synthesis vendor (e.g., GenScript, IDT, Synthego, etc.).
"""

PROMPT_PROCESS_OUTPUT_FORMAT = """Please act as an expert in molecular biology. Given the user input about output format preference, confirm the selected format. Please format your response as JSON.

User Instructions:

"In what format would you like to receive your plasmid sequence? (GenBank, FASTA, or Raw sequence)"

User Input:

{user_message}

Response format (JSON):

{{
"Thoughts": "<thoughts>",
"Selected Format": "<format>", # Select from GENBANK, FASTA, or RAW_SEQUENCE
}}"""


PROMPT_REQUEST_FINAL_SUMMARY = """
🌟 Your expression construct is complete and ready for synthesis!

Would you like to:

1️⃣ Download/save your construct design
2️⃣ Modify any aspect of your design and reorder
3️⃣ Start a new plasmid design project
"""

PROMPT_PROCESS_FINAL_SUMMARY = """Please act as an expert in molecular biology. Given the user instruction and input, determine the user's final action after receiving their construct design. Please format your response as JSON.

User Instructions:

"Your expression construct is complete. Would you like to download it, modify the design, or start over?"

User Input:

{user_message}

Response format (JSON):

{{
"Thoughts": "<thoughts>",
"Next Action": "<action>", # Select from DOWNLOAD_DESIGN, MODIFY_DESIGN, or START_NEW_PROJECT
}}"""
