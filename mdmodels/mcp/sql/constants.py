from __future__ import annotations

# JWT token claim keys for authentication and authorization
ISS = "iss"  # Issuer claim - identifies the token provider
SUBJECT = "sub"  # Subject claim - identifies the user/entity

# Tool description constants for MCP tool registration
GET_SCHEMA_DESCRIPTION = (
    "Return the full markdown data model: all fields, types, relationships, and nesting. "
    'Nested fields accept {"row_pk": <id>} to reference an existing entry instead of inlining the full object.'
)

GET_RELATIONSHIPS_DESCRIPTION = (
    "Return foreign key mappings (source/target tables and columns) for a given table. "
    "MUST be called before filtered queries and cross-table plotting to verify join paths "
    "and valid column names."
)

GENERIC_CREATE_DESCRIPTION = "Save a new {model_name} entry."
GENERIC_UPSERT_DESCRIPTION = (
    "Upsert a {model_name} entry. Provide `row_pk` to update an existing row."
)

SELECT_DESCRIPTION = (
    "SELECT from any table with optional filters and row limit (default 20). "
    "Before any filter task, first call Get_Table_Schema and Get_Table_Relationships; "
    "never assume columns such as '<parent>_id' exist."
)

AGGREGATE_DESCRIPTION = (
    "Run count/sum/avg/min/max/stddev/variance on any table with optional filters."
)

DOWNLOAD_DESCRIPTION = (
    "Fetch a single entry by primary key from any table and display it as an "
    "interactive JSON tree with Copy and Download buttons."
)

PLOT_DESCRIPTION = (
    "Query any table (with optional filters) and render the results as an "
    "interactive ECharts plot. Infer x/y axes and plot type from schema semantics "
    "and the user's intent, then pass them as 'suggested'. The user can "
    "override axis, color grouping, split, and plot type interactively. "
    "For array-based measurements, use optional series_mode to explode values "
    "into long-form points and group/color by related parent-table fields. "
    "Before choosing grouping/coloring or split_by, inspect Get_Table_Schema and "
    "Get_Table_Relationships to understand which dimensions are logically valid "
    "for this domain and reachable from the base table. "
    "Before using filters, series_mode.group_by, or split_by from another table, "
    "first call Get_Table_Schema and Get_Table_Relationships to confirm the join path "
    "from the base table and valid columns; do not assume reverse FK columns exist. "
    "Selection of split_by versus color/grouping depends on domain meaning and NLQ intent: "
    "split_by should partition/filter entities for comparison, while color/grouping should "
    "encode series within the selected partition. "
    "When the NLQ implies comparison across domain-relevant partitions, prefer split_by "
    "if a valid dimension exists. "
    "If the user asks to compare each split group separately, set subplots=true "
    "to render one panel per split_by value. "
    "Use plot_type='histogram' for a single numeric axis, 'bar' or 'boxplot' "
    "for categorical x + numeric y, and 'scatter' or 'line' for two numeric axes."
)

DATA_ENTRY_DESCRIPTION = (
    "Collect structured user input through an interactive typed form. "
    "Use this when required values are missing from context before creating/updating data. "
    "Provide clear field labels, strict field types, and enum options when choices are constrained. "
    "Enums can also be used to select existing rows for relationship linking: the model should map labels "
    "to known row identifiers and then use that mapping in follow-up upsert/create calls to connect rows. "
    "Use LaTeX in field labels/descriptions when scientific symbols, equations, or units need clear notation. "
    "Group related fields via `group` headings and keep forms compact. "
    "After the user submits, validated values are returned to the conversation so execution can continue."
)

VECTOR_SEARCH_DESCRIPTION = (
    "Cosine-similarity search (0.0=identical, 2.0=opposite). Set `table` for returned "
    "rows; optionally set `embedding_table` to search via a related table's embeddings. "
    "Check table relationships before specifying `embedding_table`. "
    "Available embedding tables:\n{embed_table_string}\nAll tables:\n{table_string}"
)

# Server behavior instructions for proper database interaction patterns
SERVER_INSTRUCTIONS = (
    "Before any Upsert_*: check existing rows via Select_Table and reuse existing rows "
    "by setting top-level `row_pk`. Never guess IDs — a wrong ID silently corrupts links. "
    'Nested objects must use {"row_pk": <id>} references instead of full inline payloads. '
    "Array-valued nested fields are append+dedupe on upsert. "
    "Before ANY filtered query (including Select_Table and Plot_Table filters), "
    "you MUST call Get_Table_Schema and Get_Table_Relationships at least once for "
    "the involved tables to verify column names, types, and join reachability."
)
