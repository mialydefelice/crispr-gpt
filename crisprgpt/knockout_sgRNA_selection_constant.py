PROMPT_REQUEST_AGENT1 = """
🧬 We could help you design the guideRNA sequence based on CRISPick (https://portals.broadinstitute.org/gppx/crispick/public) (Kim et al.,Nat Biotechnol.,2018; DeWeirdt et al.,Nat Biotechnol.,2021; Doench et al.,Nat Biotechnol.,2016; Sanson et al.,Nat Commun, 2018).

❓ Could you please describe what sgRNAs do you need? (For example, you can type in: I hope to design 2 sgRNAs targeting human EGFR; Please give me 1 sgRNA target Exon 1 of mouse Tgfbr1.)

📋 *Please include the target and species information.
📄 *Please cite the corresponding papers if you decide to use the designed sgRNA.
"""

PROMPT_PROCESS_AGENT1 = """Please act as an assistant to biologists. Given the user input about sgRNA design, extract the target gene and species, determine whether user has specified target exon. Then, suggest potential exon or exons to target and provide rationales. Please format your response following response format and make sure it is parsable by JSON.

User Input:

{user_message}

Response format: 
{{
    "Target gene": # based on user input, extract the target gene. Correct potential typo and make sure letters are in the uppercase. If not available, output NA.
    "Species": # based on user input, extract the target species. Select from human, mouse, NA.
    "Specified": # based on user input, determine whether user has specified exons to target. Only output yes or no.
    "target exon": # suggest potential exons or exon to target based on user input.
    "rationale": # based on user input, provide detailed thought process.
    "reformatted_request": #based on user input, reformat the request by interating with target exon information.
}}"""

PROMPT_REQUEST_QUESTION = """
🔍 Based on the information you provided, it may be beneficial to design sgRNAs targeting specific exons within the genes.

❓ Would you like to continue sgRNA design with the exon/exons we suggested?
"""

PROMPT_PROCESS_QUESTION = """Please act as an expert in CRISPR technology. Given the user instruction and user input, think step by step and generate a choice for the user. Please format your response and make sure it is parsable by JSON.

User Instructions:

"Based on the information you provided, it may be beneficial to design sgRNAs targeting specific exons within the genes.

Exon/exons: {target_exon}
Reason: {rationale}

Would you like to continue sgRNA design with the exon/exons we suggested?
"


User Input:

{user_message}

Response format:

{{
"Thoughts": "<thoughts>",
"Choice": "<choice>", # Select from YES, NO.
}}"""


PROMPT_PROCESS_AGENT2 = """Please act as an assistant to biologists. Given the user input and available functions, think step by step to extract the target species and help draft a seri of actions to extract information from existing sgRNA database. Please format your response following response format and make sure it is parsable by JSON.

User Input:

{user_message}

Database column:

Target Gene Symbol
Exon Number
sgRNA Cut Position (1-based)
Strand of sgRNA
On-Target Rank
Off-Target Rank
Combined Rank

Available Functions:

1. subset_value: Subset the rows where the specified column matches the given value.
    Parameters:
    column_name: The name of the column to match.
    matching_value: a list of values to match in the specified column.

2. sort: Sort the DataFrame based on values in the specified column.
    Parameters:
    column_name: The name of the column to sort by.
    ascending: Whether to sort in ascending order.

3. get: Get the top N rows of the DataFrame.
    Parameters:
    n (int): The number of top rows to return.

4. subset_between: Subset the rows where the specified column's values are between x and y (inclusive).
    Parameters:
    column_name: The name of the column to match.
    x (int): The lower bound value. Defaults to NA.
    y (int): The upper bound value. Defaults to NA.

Response format: 
{{
    "Thoughts":  # Think step by step to solve the task.
    "Species": # Extract target species from user request. Select from human and mouse. Do not output anything else.
    "Actions": 
    [ 
        {{
            "action_index": <index>, # Action index that counts from 1
            "called_function": <function>, # Function to perform. Should select one from subset,sort and get.
            "column_name": <column>, # Specified column in the column list to perform action. Output NA if not applicable.
            "matching_value": <value> # Matching values based on user input. Separate the values by comma. Output NA if not applicable.
            "ascending": <ascending> # Whether to sort in ascending order based on user input. If it's true, output TRUE, else output FALSE. Output NA if not applicable.
            "n": <n> # The number of top rows to return. Output a single number only. Default is 4. Output NA if not applicable.
            "x": <x> # The lower bound value to return. Output a single number only. Default is NA. Output NA if not applicable.
            "y": <y> # The upper bound value to return. Output a single number only. Default is NA. Output NA if not applicable.
        }},
    ] ## A list of actions.
}}"""


RESPONSE_STEP_ERROR = """
⚠️ Sorry, we could not find a sgRNA for you in our database.

While we could suggest some great resources and/or some online tools to help you design the sgRNA for your application:

1️⃣ You could use sgRNAs that have been validated. Here is Addgene's validated sgRNA database:
https://www.addgene.org/crispr/reference/grna-sequence/

2️⃣ You could use some online tools. Including:
   (i) CRISPRpick: https://portals.broadinstitute.org/gppx/crispick/public (Kim et al.,Nat Biotechnol.,2018;DeWeirdt et al.,Nat Biotechnol.,2021;Doench et al.,Nat Biotechnol.,2016;Sanson et al.,Nat Commun, 2018)
   (ii) CRISPOR: http://crispor.tefor.net/ (Concoret et al.,Nucleic Acids Res.,2018)
   (iii) Chopchop: https://chopchop.cbu.uib.no/ (Labun et al.,Nucleic Acids Res.,2019)

3️⃣ You could use the tools provided by your preferred DNA synthesize vendor.

📄 *Please cite the corresponding papers if you decide to use the sgRNA.
""" 

PROMPT_REQUEST_OFFTARGET_QUESTION = """
⚠️ Would you like to use CRISPRitz to predict sgRNA off-target effects?
"""

PROMPT_PROCESS_OFFTARGET_QUESTION = """
Please act as an expert in CRISPR technology. Given the user instruction and user input, think step by step and generate a choice for the user. Please format your response and make sure it is parsable by JSON.

User Instructions:

"Would you like to use CRISPRitz to predict sgRNA off-target effects?"

User Input:

{user_message}

Response format:

{{
"Thoughts": "<thoughts>",
"Choice": "yes or no"
}}"""
